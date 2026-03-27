const request = require('supertest')
const { app } = require('../../backend/main')

describe('Teacher Search API Tests', () => {
  let teacherToken
  let studentToken
  let teacherProfile

  beforeAll(async () => {
    // Create a teacher user and profile for testing
    const teacherResponse = await request(app)
      .post('/api/auth/signup')
      .send({
        email: 'teacher@example.com',
        password: 'teacher123',
        role: 'teacher'
      })

    teacherToken = teacherResponse.body.access_token

    // Create teacher profile
    const profileResponse = await request(app)
      .post('/api/profiles/teacher')
      .set('Authorization', `Bearer ${teacherToken}`)
      .send({
        name: 'John Smith',
        subjects_taught: ['Mathematics', 'Physics'],
        hourly_rate: 50.0,
        experience_years: 5,
        preferred_formats: ['online', 'in-person'],
        languages: ['English', 'Urdu'],
        city: 'Lahore',
        bio: 'Experienced mathematics teacher with 5 years of experience',
        qualifications: 'MSc Mathematics',
        availability: 'Weekdays 9AM-5PM'
      })

    teacherProfile = profileResponse.body

    // Create a student user for search testing
    const studentResponse = await request(app)
      .post('/api/auth/signup')
      .send({
        email: 'student@example.com',
        password: 'student123',
        role: 'student'
      })

    studentToken = studentResponse.body.access_token
  })

  describe('GET /api/teachers/search', () => {
    test('should return teachers list', async () => {
      const response = await request(app)
        .get('/api/teachers/search')
        .expect(200)

      expect(Array.isArray(response.body)).toBe(true)
      expect(response.body.length).toBeGreaterThan(0)

      const teacher = response.body[0]
      expect(teacher).toHaveProperty('id')
      expect(teacher).toHaveProperty('name')
      expect(teacher).toHaveProperty('subjects_taught')
      expect(teacher).toHaveProperty('hourly_rate')
      expect(teacher).toHaveProperty('average_rating')
    })

    test('should filter teachers by subject', async () => {
      const response = await request(app)
        .get('/api/teachers/search?subject=Mathematics')
        .expect(200)

      expect(Array.isArray(response.body)).toBe(true)
      response.body.forEach(teacher => {
        expect(teacher.subjects_taught).toContain('Mathematics')
      })
    })

    test('should filter teachers by price range', async () => {
      const response = await request(app)
        .get('/api/teachers/search?min_rate=40&max_rate=60')
        .expect(200)

      expect(Array.isArray(response.body)).toBe(true)
      response.body.forEach(teacher => {
        expect(teacher.hourly_rate).toBeGreaterThanOrEqual(40)
        expect(teacher.hourly_rate).toBeLessThanOrEqual(60)
      })
    })

    test('should filter teachers by city', async () => {
      const response = await request(app)
        .get('/api/teachers/search?city=Lahore')
        .expect(200)

      expect(Array.isArray(response.body)).toBe(true)
      response.body.forEach(teacher => {
        expect(teacher.city.toLowerCase()).toContain('lahore')
      })
    })

    test('should filter teachers by language', async () => {
      const response = await request(app)
        .get('/api/teachers/search?language=English')
        .expect(200)

      expect(Array.isArray(response.body)).toBe(true)
      response.body.forEach(teacher => {
        expect(teacher.languages).toContain('English')
      })
    })

    test('should filter teachers by preferred format', async () => {
      const response = await request(app)
        .get('/api/teachers/search?formats=online')
        .expect(200)

      expect(Array.isArray(response.body)).toBe(true)
      response.body.forEach(teacher => {
        expect(teacher.preferred_formats).toContain('online')
      })
    })

    test('should filter teachers by minimum rating', async () => {
      const response = await request(app)
        .get('/api/teachers/search?min_rating=4.0')
        .expect(200)

      expect(Array.isArray(response.body)).toBe(true)
      response.body.forEach(teacher => {
        expect(teacher.average_rating).toBeGreaterThanOrEqual(4.0)
      })
    })

    test('should sort teachers by rating', async () => {
      const response = await request(app)
        .get('/api/teachers/search?sort_by=rating')
        .expect(200)

      expect(Array.isArray(response.body)).toBe(true)
      if (response.body.length > 1) {
        for (let i = 1; i < response.body.length; i++) {
          expect(response.body[i-1].average_rating).toBeGreaterThanOrEqual(response.body[i].average_rating)
        }
      }
    })

    test('should sort teachers by price (low to high)', async () => {
      const response = await request(app)
        .get('/api/teachers/search?sort_by=price_low')
        .expect(200)

      expect(Array.isArray(response.body)).toBe(true)
      if (response.body.length > 1) {
        for (let i = 1; i < response.body.length; i++) {
          expect(response.body[i-1].hourly_rate).toBeLessThanOrEqual(response.body[i].hourly_rate)
        }
      }
    })

    test('should support pagination', async () => {
      const response = await request(app)
        .get('/api/teachers/search?page=1&per_page=5')
        .expect(200)

      expect(Array.isArray(response.body)).toBe(true)
      expect(response.body.length).toBeLessThanOrEqual(5)
    })
  })

  describe('GET /api/teachers/{teacher_id}', () => {
    test('should return teacher details', async () => {
      const response = await request(app)
        .get(`/api/teachers/${teacherProfile.id}`)
        .expect(200)

      expect(response.body).toHaveProperty('id', teacherProfile.id)
      expect(response.body).toHaveProperty('name', teacherProfile.name)
      expect(response.body).toHaveProperty('subjects_taught')
      expect(response.body).toHaveProperty('hourly_rate')
      expect(response.body).toHaveProperty('bio')
      expect(response.body).toHaveProperty('qualifications')
    })

    test('should return 404 for non-existent teacher', async () => {
      const response = await request(app)
        .get('/api/teachers/non-existent-id')
        .expect(404)

      expect(response.body.detail).toBe('Teacher not found')
    })
  })
})
