const request = require('supertest')
const { app } = require('../../backend/main')

describe('Authentication API Tests', () => {
  let testUser = {
    email: 'test@example.com',
    password: 'testpass123',
    role: 'student'
  }

  let authToken

  beforeAll(async () => {
    // Clean up any existing test user
    // This assumes you have a test cleanup endpoint
  })

  afterAll(async () => {
    // Clean up test data
  })

  describe('POST /api/auth/signup', () => {
    test('should register a new user successfully', async () => {
      const response = await request(app)
        .post('/api/auth/signup')
        .send(testUser)
        .expect(200)

      expect(response.body).toHaveProperty('access_token')
      expect(response.body).toHaveProperty('token_type', 'bearer')
      authToken = response.body.access_token
    })

    test('should reject duplicate email registration', async () => {
      const response = await request(app)
        .post('/api/auth/signup')
        .send(testUser)
        .expect(400)

      expect(response.body.detail).toBe('Email already registered')
    })

    test('should validate required fields', async () => {
      const response = await request(app)
        .post('/api/auth/signup')
        .send({ email: 'invalid' })
        .expect(422)

      expect(response.body).toHaveProperty('detail')
    })
  })

  describe('POST /api/auth/login', () => {
    test('should login with valid credentials', async () => {
      const response = await request(app)
        .post('/api/auth/login')
        .send({
          email: testUser.email,
          password: testUser.password
        })
        .expect(200)

      expect(response.body).toHaveProperty('access_token')
      expect(response.body).toHaveProperty('token_type', 'bearer')
    })

    test('should reject invalid credentials', async () => {
      const response = await request(app)
        .post('/api/auth/login')
        .send({
          email: testUser.email,
          password: 'wrongpassword'
        })
        .expect(401)

      expect(response.body.detail).toBe('Incorrect email or password')
    })

    test('should reject non-existent user', async () => {
      const response = await request(app)
        .post('/api/auth/login')
        .send({
          email: 'nonexistent@example.com',
          password: 'password'
        })
        .expect(401)

      expect(response.body.detail).toBe('Incorrect email or password')
    })
  })

  describe('GET /api/auth/me', () => {
    test('should return current user info', async () => {
      const response = await request(app)
        .get('/api/auth/me')
        .set('Authorization', `Bearer ${authToken}`)
        .expect(200)

      expect(response.body).toHaveProperty('id')
      expect(response.body).toHaveProperty('email', testUser.email)
      expect(response.body).toHaveProperty('role', testUser.role)
      expect(response.body).toHaveProperty('has_profile', false)
    })

    test('should reject request without token', async () => {
      const response = await request(app)
        .get('/api/auth/me')
        .expect(401)

      expect(response.body.detail).toBe('Not authenticated')
    })

    test('should reject invalid token', async () => {
      const response = await request(app)
        .get('/api/auth/me')
        .set('Authorization', 'Bearer invalid_token')
        .expect(401)

      expect(response.body.detail).toBe('Not authenticated')
    })
  })
})
