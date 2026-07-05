# REST API Documentation

## Overview
Complete REST API for the Online Judge platform built with Django REST Framework. Supports full CRUD operations on all models with advanced filtering, pagination, and custom actions.

## Authentication

### JWT Token Authentication
Obtain tokens using your credentials:

```bash
POST /api/auth/token/
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

Response:
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

Use the access token in subsequent requests:
```bash
Authorization: Bearer <access_token>
```

### Refresh Token
```bash
POST /api/auth/token/refresh/
Content-Type: application/json

{
  "refresh": "your_refresh_token"
}
```

### Session Authentication
Alternatively, use cookie-based session authentication after login.

---

## API Endpoints

### Users
**Base URL:** `/api/users/`

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/` | List all users (paginated) | Public |
| POST | `/` | Create new user | Authenticated |
| GET | `/{id}/` | Get user details | Authenticated |
| PUT | `/{id}/` | Update user | Authenticated |
| DELETE | `/{id}/` | Delete user | Authenticated |
| GET | `/me/` | Get current user | Authenticated |
| GET | `/{id}/profile/` | Get user's profile | Authenticated |

**List Users:**
```bash
GET /api/users/?search=john&ordering=-date_joined&page_size=10
```

Query Parameters:
- `search`: Search by username, email, first_name, or last_name
- `ordering`: Order by `id`, `date_joined`, or `username` (prefix with `-` for descending)
- `page_size`: Results per page (default: 20, max: 100)
- `page`: Page number (default: 1)

**Get Current User:**
```bash
GET /api/users/me/
Authorization: Bearer <token>
```

---

### User Profiles
**Base URL:** `/api/profiles/`

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/` | List all profiles | Authenticated |
| POST | `/` | Create profile | Authenticated |
| GET | `/{id}/` | Get profile details | Authenticated |
| PUT | `/{id}/` | Update profile | Authenticated |
| DELETE | `/{id}/` | Delete profile | Authenticated |
| GET | `/me/` | Get current user's profile | Authenticated |

**Update Profile with Photo:**
```bash
PUT /api/profiles/{id}/
Authorization: Bearer <token>
Content-Type: multipart/form-data

{
  "role": "participant",
  "photo": <image_file>
}
```

Supported photo formats: JPG, PNG, GIF, WEBP (max 5MB, min 1024x1024px)

---

### Problems
**Base URL:** `/api/problems/`

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/` | List all problems | Public |
| POST | `/` | Create problem | Authenticated |
| GET | `/{id}/` | Get problem details | Public |
| PUT | `/{id}/` | Update problem | Authenticated |
| DELETE | `/{id}/` | Delete problem | Authenticated |
| GET | `/by_difficulty/` | Filter by difficulty | Public |
| GET | `/{id}/solutions_count/` | Get solution stats | Public |

**List Problems:**
```bash
GET /api/problems/?search=arrays&difficulty=medium&ordering=-created_at&page_size=20
```

Query Parameters:
- `search`: Search by title, tags, or description
- `difficulty`: Filter by `easy`, `medium`, or `hard`
- `ordering`: Order by `created_at`, `difficulty`, or `title`

**Filter by Difficulty:**
```bash
GET /api/problems/by_difficulty/?difficulty=hard
```

**Get Solution Statistics:**
```bash
GET /api/problems/{id}/solutions_count/
```

Response:
```json
{
  "problem_id": 1,
  "total_submissions": 42,
  "accepted": 28,
  "acceptance_rate": 66.67
}
```

**Create Problem:**
```bash
POST /api/problems/
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Array Sum",
  "difficulty": "easy",
  "description": "Find the sum of all array elements",
  "constraints": "1 <= n <= 10^5",
  "input_format": "First line: n, Second line: n integers",
  "output_format": "Single integer: the sum",
  "sample_input": "3\n1 2 3",
  "sample_output": "6",
  "tags": "arrays,math"
}
```

---

### Solutions
**Base URL:** `/api/solutions/`

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/` | List user's solutions | Authenticated |
| POST | `/` | Submit solution | Authenticated |
| GET | `/{id}/` | Get solution details | Authenticated |
| GET | `/my_solutions/` | Get all my solutions | Authenticated |
| GET | `/problem_solutions/` | Get solutions for problem | Authenticated |

**Submit Solution:**
```bash
POST /api/solutions/
Authorization: Bearer <token>
Content-Type: application/json

{
  "problem": 1,
  "code": "def sum_array(arr):\n    return sum(arr)",
  "language": "python"
}
```

**Get My Solutions:**
```bash
GET /api/solutions/my_solutions/
Authorization: Bearer <token>
```

**Get Solutions for Problem:**
```bash
GET /api/solutions/problem_solutions/?problem_id=1
Authorization: Bearer <token>
```

---

### Contests
**Base URL:** `/api/contests/`

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/` | List contests | Public |
| POST | `/` | Create contest | Authenticated |
| GET | `/{id}/` | Get contest details | Public |
| PUT | `/{id}/` | Update contest | Authenticated |
| DELETE | `/{id}/` | Delete contest | Authenticated |
| GET | `/upcoming/` | Get upcoming contests | Public |
| GET | `/running/` | Get running contests | Public |
| GET | `/ended/` | Get ended contests | Public |
| POST | `/{id}/join/` | Join contest | Authenticated |
| GET | `/{id}/standings/` | Get leaderboard | Authenticated |
| GET | `/{id}/my_submissions/` | Get my submissions | Authenticated |

**List Contests:**
```bash
GET /api/contests/?search=beginner&ordering=-start_time&page_size=10
```

**Get Upcoming Contests:**
```bash
GET /api/contests/upcoming/
```

**Join Contest:**
```bash
POST /api/contests/{id}/join/
Authorization: Bearer <token>
```

Response:
```json
{
  "status": "joined",
  "message": "Successfully joined contest"
}
```

**Get Contest Standings:**
```bash
GET /api/contests/{id}/standings/
Authorization: Bearer <token>
```

Response:
```json
[
  {
    "rank": 1,
    "user": "alice",
    "user_id": 5,
    "score": 450.0,
    "submissions": 3
  },
  {
    "rank": 2,
    "user": "bob",
    "user_id": 6,
    "score": 320.0,
    "submissions": 2
  }
]
```

**Create Contest:**
```bash
POST /api/contests/
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Weekly Contest 1",
  "description": "A beginner-friendly weekly contest",
  "contest_type": "rated",
  "start_time": "2026-01-20T10:00:00Z",
  "end_time": "2026-01-20T12:00:00Z",
  "duration": "02:00:00",
  "max_participants": 100,
  "is_public": true,
  "registration_required": true
}
```

---

### Contest Problems
**Base URL:** `/api/contest-problems/`

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/` | List contest problems | Public |
| POST | `/` | Add problem to contest | Authenticated |
| GET | `/{id}/` | Get problem details | Public |
| PUT | `/{id}/` | Update problem in contest | Authenticated |
| DELETE | `/{id}/` | Remove problem from contest | Authenticated |
| GET | `/by_contest/` | Get problems in contest | Public |

**Get Problems in Contest:**
```bash
GET /api/contest-problems/by_contest/?contest_id=1
```

---

### Contest Participants
**Base URL:** `/api/contest-participants/`

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/` | List participants | Authenticated |
| GET | `/{id}/` | Get participant details | Authenticated |
| GET | `/by_contest/` | Get participants in contest | Public |

**Get Participants in Contest:**
```bash
GET /api/contest-participants/by_contest/?contest_id=1&page_size=50
```

---

### Contest Submissions
**Base URL:** `/api/contest-submissions/`

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/` | List submissions | Authenticated |
| POST | `/` | Create submission | Authenticated |
| GET | `/{id}/` | Get submission details | Authenticated |
| GET | `/by_contest/` | Get submissions in contest | Public |

**Get Submissions in Contest:**
```bash
GET /api/contest-submissions/by_contest/?contest_id=1
```

---

### Contest Announcements
**Base URL:** `/api/announcements/`

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/` | List announcements | Authenticated |
| POST | `/` | Create announcement | Authenticated |
| GET | `/{id}/` | Get announcement | Authenticated |
| PUT | `/{id}/` | Update announcement | Authenticated |
| DELETE | `/{id}/` | Delete announcement | Authenticated |
| GET | `/by_contest/` | Get contest announcements | Public |

**Get Announcements for Contest:**
```bash
GET /api/announcements/by_contest/?contest_id=1
```

**Create Announcement:**
```bash
POST /api/announcements/
Authorization: Bearer <token>
Content-Type: application/json

{
  "contest": 1,
  "title": "System Maintenance",
  "content": "The judge will undergo maintenance tonight",
  "is_important": true
}
```

---

### Admin Settings
**Base URL:** `/api/admin-settings/`

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/` | List settings | Admin only |
| PUT | `/{id}/` | Update settings | Admin only |
| GET | `/current/` | Get current settings | Authenticated |

**Get Current Settings:**
```bash
GET /api/admin-settings/current/
Authorization: Bearer <token>
```

Response:
```json
{
  "id": 1,
  "ai_review_enabled": true,
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-01-15T11:00:00Z"
}
```

---

## Response Format

All responses follow JSON format:

**Success Response (2xx):**
```json
{
  "id": 1,
  "name": "example",
  "created_at": "2026-01-15T10:00:00Z"
}
```

**Paginated Response:**
```json
{
  "count": 100,
  "next": "http://localhost:8000/api/problems/?page=2",
  "previous": null,
  "results": [...]
}
```

**Error Response (4xx/5xx):**
```json
{
  "detail": "Authentication credentials were not provided."
}
```

---

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Request successful |
| 201 | Created - Resource created |
| 204 | No Content - Successful deletion |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Missing/invalid authentication |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |

---

## Rate Limiting

API requests are rate-limited:
- **Anonymous users:** 100 requests/hour
- **Authenticated users:** 1000 requests/hour

When rate limited, response includes `Retry-After` header.

---

## Filtering & Sorting

### Search
Most list endpoints support full-text search:
```bash
GET /api/problems/?search=array
```

### Ordering
Most list endpoints support result ordering:
```bash
GET /api/users/?ordering=-date_joined
```

Prefix field with `-` for descending order.

### Pagination
```bash
GET /api/problems/?page=2&page_size=50
```

Default page size: 20, Maximum: 100

---

## Example Workflows

### 1. Create and Submit Solution
```bash
# Get token
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"john","password":"pass123"}'

# Create problem (if setter)
curl -X POST http://localhost:8000/api/problems/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{...}'

# Submit solution
curl -X POST http://localhost:8000/api/solutions/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"problem":1,"code":"...","language":"python"}'
```

### 2. Create Contest and Get Standings
```bash
# Create contest
curl -X POST http://localhost:8000/api/contests/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{...}'

# Join contest
curl -X POST http://localhost:8000/api/contests/{id}/join/ \
  -H "Authorization: Bearer <token>"

# Get standings
curl -X GET http://localhost:8000/api/contests/{id}/standings/ \
  -H "Authorization: Bearer <token>"
```

### 3. Update Profile with Photo
```bash
curl -X PUT http://localhost:8000/api/profiles/{id}/ \
  -H "Authorization: Bearer <token>" \
  -F "role=participant" \
  -F "photo=@/path/to/photo.jpg"
```

---

## Error Handling

### Example Error Responses

**Invalid Credentials:**
```json
{
  "detail": "Invalid username or password"
}
```

**Validation Error:**
```json
{
  "title": ["This field may not be blank."],
  "difficulty": ["\"xyz\" is not a valid choice."]
}
```

**Permission Denied:**
```json
{
  "detail": "You do not have permission to perform this action."
}
```

---

## Development Tools

### Test with cURL
```bash
curl -X GET http://localhost:8000/api/problems/ \
  -H "Authorization: Bearer <token>"
```

### Test with Python Requests
```python
import requests

headers = {'Authorization': f'Bearer {token}'}
response = requests.get('http://localhost:8000/api/problems/', headers=headers)
print(response.json())
```

### Test with Postman
Import the OpenAPI/Swagger documentation or create requests manually.

---

## Versioning & Changes

API version: **v1**
Last updated: 2026-07-05

For breaking changes or new features, check release notes.
