"""
Test suite for REST API endpoints
Run with: python manage.py test core.tests_api
"""
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth.models import User
from core.models import UserProfile, Problem, Solution, Contest
from django.utils import timezone
from datetime import timedelta


class UserAPITestCase(APITestCase):
    """Test User endpoints"""
    
    def setUp(self):
        """Create test user and client"""
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.user_profile = UserProfile.objects.create(user=self.user, role='participant')
    
    def test_list_users(self):
        """Test listing users"""
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_get_current_user(self):
        """Test getting current authenticated user"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/users/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')
    
    def test_get_user_profile(self):
        """Test getting user profile"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/users/{self.user.id}/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['role'], 'participant')


class UserProfileAPITestCase(APITestCase):
    """Test UserProfile endpoints"""
    
    def setUp(self):
        """Create test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser2', password='testpass123')
        self.profile = UserProfile.objects.create(user=self.user, role='participant')
    
    def test_get_my_profile(self):
        """Test getting current user's profile"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/profiles/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['role'], 'participant')
    
    def test_list_profiles(self):
        """Test listing profiles"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/profiles/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)


class ProblemAPITestCase(APITestCase):
    """Test Problem endpoints"""
    
    def setUp(self):
        """Create test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(username='setter', password='testpass123')
        self.problem = Problem.objects.create(
            title='Test Problem',
            difficulty='easy',
            description='This is a test problem',
            created_by=self.user
        )
    
    def test_list_problems(self):
        """Test listing problems (public endpoint)"""
        response = self.client.get('/api/problems/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertGreaterEqual(len(response.data['results']), 1)
    
    def test_get_problem(self):
        """Test getting problem details"""
        response = self.client.get(f'/api/problems/{self.problem.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Test Problem')
        self.assertEqual(response.data['difficulty'], 'easy')
    
    def test_filter_by_difficulty(self):
        """Test filtering problems by difficulty"""
        response = self.client.get('/api/problems/by_difficulty/?difficulty=easy')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_solutions_count(self):
        """Test getting solution statistics"""
        response = self.client.get(f'/api/problems/{self.problem.id}/solutions_count/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_submissions', response.data)
        self.assertIn('accepted', response.data)
        self.assertIn('acceptance_rate', response.data)
    
    def test_create_problem(self):
        """Test creating a problem"""
        self.client.force_authenticate(user=self.user)
        data = {
            'title': 'New Problem',
            'difficulty': 'medium',
            'description': 'A new test problem'
        }
        response = self.client.post('/api/problems/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'New Problem')


class SolutionAPITestCase(APITestCase):
    """Test Solution endpoints"""
    
    def setUp(self):
        """Create test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(username='participant', password='testpass123')
        self.user_profile = UserProfile.objects.create(user=self.user, role='participant')
        self.setter = User.objects.create_user(username='setter2', password='testpass123')
        self.problem = Problem.objects.create(
            title='Array Sum',
            difficulty='easy',
            description='Sum all array elements',
            created_by=self.setter
        )
    
    def test_submit_solution(self):
        """Test submitting a solution"""
        self.client.force_authenticate(user=self.user)
        data = {
            'problem': self.problem.id,
            'code': 'print(sum([1,2,3]))',
            'language': 'python'
        }
        response = self.client.post('/api/solutions/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['language'], 'python')
    
    def test_get_my_solutions(self):
        """Test getting current user's solutions"""
        self.client.force_authenticate(user=self.user)
        Solution.objects.create(
            problem=self.problem,
            user=self.user,
            code='print(1)',
            language='python'
        )
        response = self.client.get('/api/solutions/my_solutions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertGreaterEqual(len(response.data['results']), 1)
    
    def test_get_problem_solutions(self):
        """Test getting solutions for a problem"""
        self.client.force_authenticate(user=self.user)
        Solution.objects.create(
            problem=self.problem,
            user=self.user,
            code='print(1)',
            language='python'
        )
        response = self.client.get(f'/api/solutions/problem_solutions/?problem_id={self.problem.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)


class ContestAPITestCase(APITestCase):
    """Test Contest endpoints"""
    
    def setUp(self):
        """Create test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(username='admin', password='testpass123')
        self.user_profile = UserProfile.objects.create(user=self.user, role='admin')
        
        now = timezone.now()
        self.contest = Contest.objects.create(
            title='Test Contest',
            description='A test contest',
            contest_type='rated',
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=2),
            created_by=self.user
        )
    
    def test_list_contests(self):
        """Test listing contests"""
        response = self.client.get('/api/contests/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_get_contest(self):
        """Test getting contest details"""
        response = self.client.get(f'/api/contests/{self.contest.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Test Contest')
    
    def test_upcoming_contests(self):
        """Test getting upcoming contests"""
        response = self.client.get('/api/contests/upcoming/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_join_contest(self):
        """Test joining a contest"""
        participant = User.objects.create_user(username='participant2', password='testpass123')
        UserProfile.objects.create(user=participant, role='participant')
        self.client.force_authenticate(user=participant)
        
        response = self.client.post(f'/api/contests/{self.contest.id}/join/')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'joined')
    
    def test_get_standings(self):
        """Test getting contest standings"""
        participant = User.objects.create_user(username='participant3', password='testpass123')
        UserProfile.objects.create(user=participant, role='participant')
        
        self.client.force_authenticate(user=participant)
        self.client.post(f'/api/contests/{self.contest.id}/join/')
        
        response = self.client.get(f'/api/contests/{self.contest.id}/standings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)


class PaginationTestCase(APITestCase):
    """Test pagination functionality"""
    
    def setUp(self):
        """Create multiple users for pagination testing"""
        self.client = APIClient()
        for i in range(25):
            User.objects.create_user(username=f'user{i}', password='testpass')
    
    def test_pagination_default(self):
        """Test default pagination"""
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 20)
        self.assertIsNotNone(response.data['next'])
    
    def test_pagination_custom_page_size(self):
        """Test custom page size"""
        response = self.client.get('/api/users/?page_size=10')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)
    
    def test_pagination_second_page(self):
        """Test getting second page"""
        response = self.client.get('/api/users/?page=2&page_size=10')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)


class SearchFilterTestCase(APITestCase):
    """Test search and filter functionality"""
    
    def setUp(self):
        """Create test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(username='john_doe', email='john@example.com')
        User.objects.create_user(username='jane_smith', email='jane@example.com')
    
    def test_search_by_username(self):
        """Test searching by username"""
        response = self.client.get('/api/users/?search=john')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should find john_doe
        usernames = [u['username'] for u in response.data['results']]
        self.assertIn('john_doe', usernames)
    
    def test_search_by_email(self):
        """Test searching by email"""
        response = self.client.get('/api/users/?search=jane')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
