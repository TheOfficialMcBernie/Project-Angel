import pytest
import json
from app import create_app, db, User, Task, AuditLog, UserRole

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def create_user(client, username, email, password, role=UserRole.USER.value):
    """Helper to create a user"""
    user = User(username=username, email=email, role=role, is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user

def get_token(client, username, password):
    """Helper to get JWT token for a user"""
    response = client.post('/auth/login', json={
        'username': username,
        'password': password
    })
    return response.get_json()['access_token']

@pytest.fixture
def admin_user(app):
    """Create an admin user"""
    with app.app_context():
        return create_user(None, 'admin_test', 'admin@test.com', 'admin123', UserRole.ADMIN.value)

@pytest.fixture
def regular_user(app):
    """Create a regular user"""
    with app.app_context():
        return create_user(None, 'user_test', 'user@test.com', 'user123', UserRole.USER.value)

@pytest.fixture
def admin_headers(client, admin_user):
    """Get auth headers for admin"""
    token = get_token(client, 'admin_test', 'admin123')
    return {'Authorization': f'Bearer {token}'}

@pytest.fixture
def user_headers(client, regular_user):
    """Get auth headers for regular user"""
    token = get_token(client, 'user_test', 'user123')
    return {'Authorization': f'Bearer {token}'}

class TestHealth:
    def test_health_check(self, client):
        response = client.get('/health')
        assert response.status_code == 200
        assert response.get_json()['status'] == 'healthy'

class TestAuth:
    def test_register_success(self, client):
        response = client.post('/auth/register', json={
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'securepass'
        })
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['user']['username'] == 'newuser'
        assert data['user']['role'] == UserRole.USER.value
        assert 'access_token' in data
    
    def test_login_success(self, client, regular_user):
        response = client.post('/auth/login', json={
            'username': 'user_test',
            'password': 'user123'
        })
        assert response.status_code == 200
        assert 'access_token' in response.get_json()
    
    def test_login_disabled_user(self, client, app):
        with app.app_context():
            user = User.query.filter_by(username='user_test').first()
            user.is_active = False
            db.session.commit()
        
        response = client.post('/auth/login', json={
            'username': 'user_test',
            'password': 'user123'
        })
        assert response.status_code == 403

class TestRBAC:
    def test_admin_can_list_all_users(self, client, admin_headers, regular_user):
        response = client.get('/api/admin/users', headers=admin_headers)
        assert response.status_code == 200
        users = response.get_json()
        assert len(users) >= 1
    
    def test_regular_user_cannot_list_users(self, client, user_headers):
        response = client.get('/api/admin/users', headers=user_headers)
        assert response.status_code == 403
    
    def test_admin_can_update_user_role(self, client, admin_headers, app, regular_user):
        with app.app_context():
            user_id = User.query.filter_by(username='user_test').first().id
        
        response = client.put(f'/api/admin/users/{user_id}/role', 
            headers=admin_headers,
            json={'role': UserRole.MODERATOR.value}
        )
        assert response.status_code == 200
        assert response.get_json()['user']['role'] == UserRole.MODERATOR.value
    
    def test_regular_user_cannot_update_roles(self, client, user_headers, admin_user):
        response = client.put(f'/api/admin/users/{admin_user.id}/role',
            headers=user_headers,
            json={'role': UserRole.USER.value}
        )
        assert response.status_code == 403
    
    def test_admin_can_disable_user(self, client, admin_headers, regular_user):
        response = client.put(f'/api/admin/users/{regular_user.id}/disable',
            headers=admin_headers
        )
        assert response.status_code == 200
        assert response.get_json()['user']['is_active'] == False
    
    def test_admin_can_enable_user(self, client, admin_headers, app):
        with app.app_context():
            user = User.query.filter_by(username='user_test').first()
            user.is_active = False
            db.session.commit()
            user_id = user.id
        
        response = client.put(f'/api/admin/users/{user_id}/enable',
            headers=admin_headers
        )
        assert response.status_code == 200
        assert response.get_json()['user']['is_active'] == True

class TestTaskPermissions:
    def test_user_can_create_own_task(self, client, user_headers):
        response = client.post('/api/tasks',
            headers=user_headers,
            json={'title': 'My Task', 'description': 'My description'}
        )
        assert response.status_code == 201
    
    def test_disabled_user_cannot_create_task(self, client, app):
        with app.app_context():
            user = User.query.filter_by(username='user_test').first()
            user.is_active = False
            db.session.commit()
        
        token = get_token(client, 'user_test', 'user123')
        headers = {'Authorization': f'Bearer {token}'}
        
        response = client.post('/api/tasks',
            headers=headers,
            json={'title': 'Task', 'description': 'desc'}
        )
        assert response.status_code == 403
    
    def test_user_can_only_view_own_tasks(self, client, user_headers, app):
        with app.app_context():
            user1 = User.query.filter_by(username='user_test').first()
            task1 = Task(title='User1 Task', user_id=user1.id)
            db.session.add(task1)
            db.session.commit()
            task1_id = task1.id
        
        # Create another user
        client.post('/auth/register', json={
            'username': 'user2', 'email': 'user2@test.com', 'password': 'pass'
        })
        token2 = get_token(client, 'user2', 'pass')
        headers2 = {'Authorization': f'Bearer {token2}'}
        
        # User1 tries to access user2's task
        response = client.get(f'/api/tasks/{task1_id}', headers=headers2)
        assert response.status_code == 403
    
    def test_admin_can_view_all_tasks(self, client, admin_headers, app):
        with app.app_context():
            user = User.query.filter_by(username='user_test').first()
            task = Task(title='User Task', user_id=user.id)
            db.session.add(task)
            db.session.commit()
        
        response = client.get('/api/tasks', headers=admin_headers)
        assert response.status_code == 200
        tasks = response.get_json()
        assert len(tasks) >= 1
    
    def test_user_can_update_own_task(self, client, user_headers, app):
        with app.app_context():
            user = User.query.filter_by(username='user_test').first()
            task = Task(title='Original', user_id=user.id)
            db.session.add(task)
            db.session.commit()
            task_id = task.id
        
        response = client.put(f'/api/tasks/{task_id}',
            headers=user_headers,
            json={'title': 'Updated'}
        )
        assert response.status_code == 200
        assert response.get_json()['title'] == 'Updated'
    
    def test_user_cannot_update_others_task(self, client, app):
        with app.app_context():
            user1 = User.query.filter_by(username='user_test').first()
            task = Task(title='User1 Task', user_id=user1.id)
            db.session.add(task)
            db.session.commit()
            task_id = task.id
        
        # Create another user
        client.post('/auth/register', json={
            'username': 'user2', 'email': 'user2@test.com', 'password': 'pass'
        })
        token2 = get_token(client, 'user2', 'pass')
        headers2 = {'Authorization': f'Bearer {token2}'}
        
        response = client.put(f'/api/tasks/{task_id}',
            headers=headers2,
            json={'title': 'Hacked'}
        )
        assert response.status_code == 403
    
    def test_admin_can_delete_any_task(self, client, admin_headers, app):
        with app.app_context():
            user = User.query.filter_by(username='user_test').first()
            task = Task(title='Task', user_id=user.id)
            db.session.add(task)
            db.session.commit()
            task_id = task.id
        
        response = client.delete(f'/api/tasks/{task_id}', headers=admin_headers)
        assert response.status_code == 204

class TestAuditLogs:
    def test_admin_can_view_audit_logs(self, client, admin_headers):
        response = client.get('/api/admin/audit-logs', headers=admin_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert 'logs' in data
        assert 'total' in data
    
    def test_regular_user_cannot_view_audit_logs(self, client, user_headers):
        response = client.get('/api/admin/audit-logs', headers=user_headers)
        assert response.status_code == 403
    
    def test_actions_are_logged(self, client, user_headers, app):
        client.post('/api/tasks',
            headers=user_headers,
            json={'title': 'Test', 'description': 'desc'}
        )
        
        with app.app_context():
            logs = AuditLog.query.filter_by(action='CREATE_TASK').all()
            assert len(logs) >= 1

class TestCurrentUser:
    def test_get_current_user_profile(self, client, user_headers):
        response = client.get('/api/me', headers=user_headers)
        assert response.status_code == 200
        user_data = response.get_json()
        assert user_data['username'] == 'user_test'
        assert user_data['role'] == UserRole.USER.value
