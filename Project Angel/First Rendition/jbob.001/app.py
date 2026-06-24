from flask import Flask, jsonify, request, g
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
from functools import wraps
from enum import Enum
import logging
import time
import uuid
from pythonjsonlogger import jsonlogger
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CollectorRegistry, REGISTRY

db = SQLAlchemy()
jwt = JWTManager()

# Prometheus metrics
request_count = Counter(
    'app_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'app_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

active_requests = Gauge(
    'app_active_requests',
    'Active HTTP requests'
)

db_query_duration = Histogram(
    'app_db_query_duration_seconds',
    'Database query duration',
    ['operation']
)

errors_count = Counter(
    'app_errors_total',
    'Total errors',
    ['error_type', 'endpoint']
)

# Setup structured logging
def setup_logging():
    """Configure JSON structured logging"""
    log_handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter()
    log_handler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.addHandler(log_handler)
    logger.setLevel(logging.INFO)
    
    return logger

logger = setup_logging()

class UserRole(Enum):
    """User roles for RBAC"""
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"

# Models (defined at module level)
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default=UserRole.USER.value, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    tasks = db.relationship('Task', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self, include_sensitive=False):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat()
        }

class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'completed': self.completed,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat()
        }

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    resource = db.Column(db.String(100), nullable=False)
    resource_id = db.Column(db.Integer)
    changes = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'resource': self.resource,
            'resource_id': self.resource_id,
            'changes': self.changes,
            'ip_address': self.ip_address,
            'timestamp': self.timestamp.isoformat()
        }

def role_required(*roles):
    """Decorator to enforce role-based access control"""
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            user_id = int(get_jwt_identity())
            user = User.query.get(user_id)
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            if user.role not in roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def create_app():
    app = Flask(__name__)
    
    DATABASE_URL = os.getenv(
        'DATABASE_URL',
        'postgresql://appuser:[REDACTED]@db:5432/appdb'
    )
    
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)
    
    db.init_app(app)
    jwt.init_app(app)
    
    # Request logging middleware
    @app.before_request
    def before_request():
        """Before each request: start timer, assign correlation ID, increment active requests"""
        g.start_time = time.time()
        g.request_id = str(uuid.uuid4())
        g.user_id = None
        active_requests.inc()
        
        logger.info('request_started', extra={
            'request_id': g.request_id,
            'method': request.method,
            'path': request.path,
            'remote_addr': request.remote_addr
        })
    
    @app.after_request
    def after_request(response):
        """After each request: log duration, update metrics"""
        duration = time.time() - g.start_time
        active_requests.dec()
        
        # Update metrics
        endpoint = request.endpoint or 'unknown'
        request_count.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code
        ).inc()
        
        request_duration.labels(
            method=request.method,
            endpoint=endpoint
        ).observe(duration)
        
        # Log request
        logger.info('request_completed', extra={
            'request_id': g.request_id,
            'method': request.method,
            'path': request.path,
            'status': response.status_code,
            'duration_ms': round(duration * 1000, 2),
            'user_id': g.user_id,
            'remote_addr': request.remote_addr
        })
        
        return response
    
    @app.errorhandler(Exception)
    def handle_error(error):
        """Global error handler with logging"""
        endpoint = request.endpoint or 'unknown'
        errors_count.labels(
            error_type=type(error).__name__,
            endpoint=endpoint
        ).inc()
        
        logger.error('request_error', extra={
            'request_id': g.request_id,
            'error': str(error),
            'error_type': type(error).__name__,
            'method': request.method,
            'path': request.path,
            'user_id': g.user_id
        })
        
        return jsonify({'error': 'Internal server error'}), 500
    
    with app.app_context():
        try:
            db.create_all()
            # Create default admin user if none exists
            if not User.query.filter_by(role=UserRole.ADMIN.value).first():
                admin = User(
                    username='admin',
                    email='admin@example.com',
                    role=UserRole.ADMIN.value,
                    is_active=True
                )
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                print("✓ Default admin user created (username: admin, password: admin123)")
        except Exception as e:
            print(f"Deferred DB init: {e}")
    
    def log_audit(user_id, action, resource, resource_id=None, changes=None):
        """Log an action for audit trail"""
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            changes=changes,
            ip_address=request.remote_addr
        )
        db.session.add(log_entry)
        db.session.commit()
        
        logger.info('audit_log', extra={
            'user_id': user_id,
            'action': action,
            'resource': resource,
            'resource_id': resource_id
        })
    
    # Auth Routes
    @app.route('/auth/register', methods=['POST'])
    def register():
        data = request.get_json()
        
        if not data or not data.get('username') or not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Missing required fields'}), 400
        
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 409
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 409
        
        user = User(
            username=data['username'],
            email=data['email'],
            role=UserRole.USER.value,
            is_active=True
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        g.user_id = user.id
        log_audit(user.id, 'REGISTER', 'User', user.id)
        
        access_token = create_access_token(identity=str(user.id))
        return jsonify({
            'message': 'User created successfully',
            'user': user.to_dict(),
            'access_token': access_token
        }), 201
    
    @app.route('/auth/login', methods=['POST'])
    def login():
        data = request.get_json()
        
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({'error': 'Missing username or password'}), 400
        
        user = User.query.filter_by(username=data['username']).first()
        
        if not user or not user.check_password(data['password']):
            return jsonify({'error': 'Invalid username or password'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'User account is disabled'}), 403
        
        g.user_id = user.id
        log_audit(user.id, 'LOGIN', 'User', user.id)
        
        access_token = create_access_token(identity=str(user.id))
        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict(),
            'access_token': access_token
        }), 200
    
    # Health check
    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({'status': 'healthy'}), 200
    
    # Metrics endpoint (Prometheus compatible)
    @app.route('/metrics', methods=['GET'])
    def metrics():
        """Prometheus metrics endpoint"""
        return generate_latest(REGISTRY), 200, {'Content-Type': 'text/plain; charset=utf-8'}
    
    # User Management (Admin only)
    @app.route('/api/admin/users', methods=['GET'])
    @role_required(UserRole.ADMIN.value)
    def list_users():
        """Admin endpoint: list all users"""
        user_id = int(get_jwt_identity())
        g.user_id = user_id
        users = User.query.all()
        return jsonify([user.to_dict() for user in users]), 200
    
    @app.route('/api/admin/users/<int:user_id>/role', methods=['PUT'])
    @role_required(UserRole.ADMIN.value)
    def update_user_role(user_id):
        """Admin endpoint: update user role"""
        current_user_id = int(get_jwt_identity())
        g.user_id = current_user_id
        
        target_user = User.query.get(user_id)
        
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        new_role = data.get('role')
        
        # Validate role
        valid_roles = [role.value for role in UserRole]
        if new_role not in valid_roles:
            return jsonify({'error': f'Invalid role. Must be one of: {valid_roles}'}), 400
        
        old_role = target_user.role
        target_user.role = new_role
        db.session.commit()
        
        log_audit(current_user_id, 'UPDATE_ROLE', 'User', user_id, 
                 {'old_role': old_role, 'new_role': new_role})
        
        return jsonify({
            'message': f'User role updated from {old_role} to {new_role}',
            'user': target_user.to_dict()
        }), 200
    
    @app.route('/api/admin/users/<int:user_id>/disable', methods=['PUT'])
    @role_required(UserRole.ADMIN.value)
    def disable_user(user_id):
        """Admin endpoint: disable user account"""
        current_user_id = int(get_jwt_identity())
        g.user_id = current_user_id
        
        target_user = User.query.get(user_id)
        
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        
        target_user.is_active = False
        db.session.commit()
        
        log_audit(current_user_id, 'DISABLE_USER', 'User', user_id)
        
        return jsonify({
            'message': 'User account disabled',
            'user': target_user.to_dict()
        }), 200
    
    @app.route('/api/admin/users/<int:user_id>/enable', methods=['PUT'])
    @role_required(UserRole.ADMIN.value)
    def enable_user(user_id):
        """Admin endpoint: enable user account"""
        current_user_id = int(get_jwt_identity())
        g.user_id = current_user_id
        
        target_user = User.query.get(user_id)
        
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        
        target_user.is_active = True
        db.session.commit()
        
        log_audit(current_user_id, 'ENABLE_USER', 'User', user_id)
        
        return jsonify({
            'message': 'User account enabled',
            'user': target_user.to_dict()
        }), 200
    
    @app.route('/api/admin/audit-logs', methods=['GET'])
    @role_required(UserRole.ADMIN.value)
    def get_audit_logs():
        """Admin endpoint: view audit logs"""
        user_id = int(get_jwt_identity())
        g.user_id = user_id
        
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset).all()
        total = AuditLog.query.count()
        
        return jsonify({
            'total': total,
            'limit': limit,
            'offset': offset,
            'logs': [log.to_dict() for log in logs]
        }), 200
    
    # Task Routes (Protected)
    @app.route('/api/tasks', methods=['GET'])
    @jwt_required()
    def get_tasks():
        """Get user's tasks (or all tasks for admin)"""
        user_id = int(get_jwt_identity())
        g.user_id = user_id
        user = User.query.get(user_id)
        
        if user.role == UserRole.ADMIN.value:
            tasks = Task.query.all()
        else:
            tasks = Task.query.filter_by(user_id=user_id).all()
        
        return jsonify([task.to_dict() for task in tasks]), 200
    
    @app.route('/api/tasks', methods=['POST'])
    @jwt_required()
    def create_task():
        """Create a task (requires active account)"""
        user_id = int(get_jwt_identity())
        g.user_id = user_id
        user = User.query.get(user_id)
        
        if not user.is_active:
            return jsonify({'error': 'User account is disabled'}), 403
        
        data = request.get_json()
        
        if not data or not data.get('title'):
            return jsonify({'error': 'Title is required'}), 400
        
        task = Task(
            title=data['title'],
            description=data.get('description', ''),
            user_id=user_id
        )
        db.session.add(task)
        db.session.commit()
        
        log_audit(user_id, 'CREATE_TASK', 'Task', task.id)
        
        return jsonify(task.to_dict()), 201
    
    @app.route('/api/tasks/<int:task_id>', methods=['GET'])
    @jwt_required()
    def get_task(task_id):
        """Get a specific task"""
        user_id = int(get_jwt_identity())
        g.user_id = user_id
        user = User.query.get(user_id)
        task = Task.query.get(task_id)
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        if user.role != UserRole.ADMIN.value and task.user_id != user_id:
            return jsonify({'error': 'Insufficient permissions'}), 403
        
        return jsonify(task.to_dict()), 200
    
    @app.route('/api/tasks/<int:task_id>', methods=['PUT'])
    @jwt_required()
    def update_task(task_id):
        """Update a task (user can update own, admin can update any)"""
        user_id = int(get_jwt_identity())
        g.user_id = user_id
        user = User.query.get(user_id)
        task = Task.query.get(task_id)
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        if user.role != UserRole.ADMIN.value and task.user_id != user_id:
            return jsonify({'error': 'Insufficient permissions'}), 403
        
        data = request.get_json()
        if 'title' in data:
            task.title = data['title']
        if 'description' in data:
            task.description = data['description']
        if 'completed' in data:
            task.completed = data['completed']
        
        db.session.commit()
        
        log_audit(user_id, 'UPDATE_TASK', 'Task', task_id)
        
        return jsonify(task.to_dict()), 200
    
    @app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
    @jwt_required()
    def delete_task(task_id):
        """Delete a task (user can delete own, admin can delete any)"""
        user_id = int(get_jwt_identity())
        g.user_id = user_id
        user = User.query.get(user_id)
        task = Task.query.get(task_id)
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        if user.role != UserRole.ADMIN.value and task.user_id != user_id:
            return jsonify({'error': 'Insufficient permissions'}), 403
        
        db.session.delete(task)
        db.session.commit()
        
        log_audit(user_id, 'DELETE_TASK', 'Task', task_id)
        
        return '', 204
    
    @app.route('/api/me', methods=['GET'])
    @jwt_required()
    def get_current_user():
        """Get current user profile"""
        user_id = int(get_jwt_identity())
        g.user_id = user_id
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify(user.to_dict()), 200
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
