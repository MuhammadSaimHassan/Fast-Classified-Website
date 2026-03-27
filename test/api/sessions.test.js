const request = require('supertest')
const { app } = require('../../backend/main')

describe('Session Management API Tests', () => {
  let teacherToken
  let studentToken
  let teacherProfile
  let studentProfile
  let sessionId

  beforeAll(async () => {
    // Create teacher
    const teacherResponse = await request(app)
      .post('/api/auth/signup')
      .send({
        email: 'teacher2@example.com',
        password: 'teacher123',
        role: 'teacher'
      })

    teacherToken = teacherResponse.body.access_token

    teacherProfile = await request(app)
      .post('/api/profiles/teacher')
      .set('Authorization', `Bearer ${teacherToken}`)
      .send({
        name: 'Jane Doe',
        subjects_taught: ['English', 'Literature'],
        hourly_rate: 40.0,
        experience_years: 3,
        preferred_formats: ['online'],
        languages: ['English'],
        city: 'Karachi',
        bio: 'Experienced English teacher',
        qualifications: 'BA English Literature',
        availability: 'Flexible hours'
      })
    teacherProfile = teacherProfile.body

    // Create student
    const studentResponse = await request(app)
      .post('/api/auth/signup')
      .send({
        email: 'student2@example.com',
        password: 'student123',
        role: 'student'
      })

    studentToken = studentResponse.body.access_token

    studentProfile = await request(app)
      .post('/api/profiles/student')
      .set('Authorization', `Bearer ${studentToken}`)
      .send({
        name: 'Alice Johnson',
        grade_level: 'Grade 10',
        subjects_needed: ['English', 'Mathematics'],
        learning_goals: 'Improve English writing skills',
        preferred_format: 'online',
        available_days: ['Monday', 'Wednesday', 'Friday'],
        budget_range: '30-50 per hour'
      })
    studentProfile = studentProfile.body
  })

  describe('POST /api/sessions/book', () => {
    test('should book a session successfully', async () => {
      const sessionData = {
        teacher_id: teacherProfile.id,
        subject: 'English',
        topic: 'Essay Writing',
        scheduled_date: '2024-12-01',
        scheduled_time: '14:00',
        duration: 1.5,
        is_recurring: false,
        notes: 'Need help with essay structure'
      }

      const response = await request(app)
        .post('/api/sessions/book')
        .set('Authorization', `Bearer ${studentToken}`)
        .send(sessionData)
        .expect(200)

      expect(response.body).toHaveProperty('id')
      expect(response.body).toHaveProperty('student_name', studentProfile.name)
      expect(response.body).toHaveProperty('teacher_name', teacherProfile.name)
      expect(response.body).toHaveProperty('subject', sessionData.subject)
      expect(response.body).toHaveProperty('topic', sessionData.topic)
      expect(response.body).toHaveProperty('total_amount', teacherProfile.hourly_rate * sessionData.duration)
      expect(response.body).toHaveProperty('status', 'pending')

      sessionId = response.body.id
    })

    test('should reject booking without student profile', async () => {
      // Create student without profile
      const noProfileStudent = await request(app)
        .post('/api/auth/signup')
        .send({
          email: 'noprofile@example.com',
          password: 'student123',
          role: 'student'
        })

      const sessionData = {
        teacher_id: teacherProfile.id,
        subject: 'English',
        topic: 'Grammar',
        scheduled_date: '2024-12-02',
        scheduled_time: '15:00',
        duration: 1.0,
        is_recurring: false
      }

      const response = await request(app)
        .post('/api/sessions/book')
        .set('Authorization', `Bearer ${noProfileStudent.body.access_token}`)
        .send(sessionData)
        .expect(400)

      expect(response.body.detail).toBe('Please create a profile first')
    })

    test('should reject booking with non-existent teacher', async () => {
      const sessionData = {
        teacher_id: 'non-existent-id',
        subject: 'English',
        topic: 'Grammar',
        scheduled_date: '2024-12-02',
        scheduled_time: '15:00',
        duration: 1.0,
        is_recurring: false
      }

      const response = await request(app)
        .post('/api/sessions/book')
        .set('Authorization', `Bearer ${studentToken}`)
        .send(sessionData)
        .expect(404)

      expect(response.body.detail).toBe('Teacher not found')
    })

    test('should reject booking by teacher', async () => {
      const sessionData = {
        teacher_id: teacherProfile.id,
        subject: 'English',
        topic: 'Grammar',
        scheduled_date: '2024-12-02',
        scheduled_time: '15:00',
        duration: 1.0,
        is_recurring: false
      }

      const response = await request(app)
        .post('/api/sessions/book')
        .set('Authorization', `Bearer ${teacherToken}`)
        .send(sessionData)
        .expect(403)

      expect(response.body.detail).toBe('Only students can book sessions')
    })
  })

  describe('GET /api/sessions', () => {
    test('should return student sessions', async () => {
      const response = await request(app)
        .get('/api/sessions')
        .set('Authorization', `Bearer ${studentToken}`)
        .expect(200)

      expect(Array.isArray(response.body)).toBe(true)
      expect(response.body.length).toBeGreaterThan(0)

      const session = response.body.find(s => s.id === sessionId)
      expect(session).toBeDefined()
      expect(session).toHaveProperty('subject', 'English')
      expect(session).toHaveProperty('teacher_name', teacherProfile.name)
    })

    test('should return teacher sessions', async () => {
      const response = await request(app)
        .get('/api/sessions')
        .set('Authorization', `Bearer ${teacherToken}`)
        .expect(200)

      expect(Array.isArray(response.body)).toBe(true)
      expect(response.body.length).toBeGreaterThan(0)

      const session = response.body.find(s => s.id === sessionId)
      expect(session).toBeDefined()
      expect(session).toHaveProperty('subject', 'English')
      expect(session).toHaveProperty('student_name', studentProfile.name)
    })

    test('should filter sessions by status', async () => {
      const response = await request(app)
        .get('/api/sessions?status=pending')
        .set('Authorization', `Bearer ${studentToken}`)
        .expect(200)

      expect(Array.isArray(response.body)).toBe(true)
      response.body.forEach(session => {
        expect(session.status).toBe('pending')
      })
    })

    test('should support pagination', async () => {
      const response = await request(app)
        .get('/api/sessions?page=1&per_page=10')
        .set('Authorization', `Bearer ${studentToken}`)
        .expect(200)

      expect(Array.isArray(response.body)).toBe(true)
      expect(response.body.length).toBeLessThanOrEqual(10)
    })
  })

  describe('PATCH /api/sessions/{session_id}', () => {
    test('should update session status by teacher', async () => {
      const updateData = {
        status: 'confirmed'
      }

      const response = await request(app)
        .patch(`/api/sessions/${sessionId}`)
        .set('Authorization', `Bearer ${teacherToken}`)
        .send(updateData)
        .expect(200)

      expect(response.body).toHaveProperty('status', 'confirmed')
    })

    test('should reject update by unauthorized user', async () => {
      // Create another student
      const otherStudent = await request(app)
        .post('/api/auth/signup')
        .send({
          email: 'other@example.com',
          password: 'student123',
          role: 'student'
        })

      const updateData = {
        status: 'cancelled'
      }

      const response = await request(app)
        .patch(`/api/sessions/${sessionId}`)
        .set('Authorization', `Bearer ${otherStudent.body.access_token}`)
        .send(updateData)
        .expect(403)

      expect(response.body.detail).toBe('Access denied')
    })

    test('should return 404 for non-existent session', async () => {
      const updateData = {
        status: 'confirmed'
      }

      const response = await request(app)
        .patch('/api/sessions/non-existent-id')
        .set('Authorization', `Bearer ${teacherToken}`)
        .send(updateData)
        .expect(404)

      expect(response.body.detail).toBe('Session not found')
    })
  })
})
