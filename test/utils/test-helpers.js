// Test data helpers and utilities for Fast Classified testing

const request = require('supertest')
const { app } = require('../backend/main')

class TestHelpers {
  constructor() {
    this.baseURL = 'http://localhost:8000'
    this.testUsers = new Map()
    this.testSessions = []
    this.testTeachers = []
    this.testStudents = []
  }

  // User creation helpers
  async createTestUser(userData) {
    const response = await request(app)
      .post('/api/auth/signup')
      .send(userData)
      .expect(200)

    const user = {
      ...userData,
      token: response.body.access_token,
      id: this.extractUserIdFromToken(response.body.access_token)
    }

    this.testUsers.set(userData.email, user)
    return user
  }

  async createTestTeacher(teacherData) {
    const user = await this.createTestUser({
      email: teacherData.email,
      password: teacherData.password,
      role: 'teacher'
    })

    const profileResponse = await request(app)
      .post('/api/profiles/teacher')
      .set('Authorization', `Bearer ${user.token}`)
      .send(teacherData.profile)
      .expect(200)

    const teacher = {
      ...user,
      profile: profileResponse.body,
      profileId: profileResponse.body.id
    }

    this.testTeachers.push(teacher)
    return teacher
  }

  async createTestStudent(studentData) {
    const user = await this.createTestUser({
      email: studentData.email,
      password: studentData.password,
      role: 'student'
    })

    const profileResponse = await request(app)
      .post('/api/profiles/student')
      .set('Authorization', `Bearer ${user.token}`)
      .send(studentData.profile)
      .expect(200)

    const student = {
      ...user,
      profile: profileResponse.body,
      profileId: profileResponse.body.id
    }

    this.testStudents.push(student)
    return student
  }

  // Session management helpers
  async createTestSession(sessionData) {
    const response = await request(app)
      .post('/api/sessions/book')
      .set('Authorization', `Bearer ${sessionData.studentToken}`)
      .send({
        teacher_id: sessionData.teacherId,
        subject: sessionData.subject,
        topic: sessionData.topic,
        scheduled_date: sessionData.date,
        scheduled_time: sessionData.time,
        duration: sessionData.duration,
        is_recurring: sessionData.is_recurring || false
      })
      .expect(200)

    const session = {
      ...response.body,
      id: response.body.id
    }

    this.testSessions.push(session)
    return session
  }

  async completeTestSession(sessionId, teacherToken) {
    await request(app)
      .patch(`/api/sessions/${sessionId}`)
      .set('Authorization', `Bearer ${teacherToken}`)
      .send({ status: 'completed' })
      .expect(200)
  }

  async payForSession(sessionId, studentToken) {
    // Simulate payment completion
    await request(app)
      .post('/api/test/simulate-payment')
      .send({ session_id: sessionId })
      .expect(200)
  }

  // Review helpers
  async createTestReview(reviewData) {
    const response = await request(app)
      .post('/api/reviews')
      .set('Authorization', `Bearer ${reviewData.studentToken}`)
      .send({
        session_id: reviewData.sessionId,
        rating: reviewData.rating,
        review_text: reviewData.text
      })
      .expect(200)

    return response.body
  }

  // Message helpers
  async createTestConversation(participant1Token, participant2Id) {
    const response = await request(app)
      .post('/api/messages')
      .set('Authorization', `Bearer ${participant1Token}`)
      .send({
        receiver_id: participant2Id,
        content: 'Test conversation starter'
      })
      .expect(200)

    return response.body
  }

  // Wallet helpers
  async addWalletBalance(userToken, amount) {
    await request(app)
      .post('/api/test/add-wallet-balance')
      .set('Authorization', `Bearer ${userToken}`)
      .send({ amount })
      .expect(200)
  }

  // Cleanup helpers
  async cleanupTestData() {
    // Delete test sessions
    for (const session of this.testSessions) {
      try {
        await request(app).delete(`/api/sessions/${session.id}`)
      } catch (error) {
        console.warn(`Failed to delete session ${session.id}`)
      }
    }

    // Delete test users (this would require admin privileges)
    for (const [email, user] of this.testUsers) {
      try {
        await request(app)
          .delete(`/api/admin/users/${user.id}`)
          .set('Authorization', `Bearer ${this.adminToken}`)
      } catch (error) {
        console.warn(`Failed to delete user ${email}`)
      }
    }

    this.reset()
  }

  reset() {
    this.testUsers.clear()
    this.testSessions = []
    this.testTeachers = []
    this.testStudents = []
  }

  // Utility methods
  extractUserIdFromToken(token) {
    // This is a simplified extraction - in real JWT you'd decode properly
    try {
      const payload = JSON.parse(Buffer.from(token.split('.')[1], 'base64').toString())
      return payload.sub
    } catch (error) {
      return null
    }
  }

  generateTestEmail(prefix = 'test') {
    return `${prefix}${Date.now()}@example.com`
  }

  generateTestData(type) {
    const timestamp = Date.now()

    switch (type) {
      case 'teacher':
        return {
          email: `teacher${timestamp}@example.com`,
          password: 'teacher123',
          role: 'teacher',
          profile: {
            name: `Dr. Test Teacher ${timestamp}`,
            subjects_taught: ['Mathematics', 'Physics'],
            hourly_rate: 75.0,
            experience_years: 8,
            preferred_formats: ['online', 'in-person'],
            languages: ['English', 'Spanish'],
            city: 'Lahore',
            bio: 'Experienced educator with advanced degrees in Mathematics and Physics.',
            qualifications: 'PhD Mathematics, MSc Physics',
            availability: 'Monday-Friday: 9AM-6PM'
          }
        }

      case 'student':
        return {
          email: `student${timestamp}@example.com`,
          password: 'student123',
          role: 'student',
          profile: {
            name: `Test Student ${timestamp}`,
            grade_level: 'Grade 11',
            subjects_needed: ['Mathematics', 'Physics'],
            learning_goals: 'Prepare for college entrance exams',
            preferred_format: 'online',
            available_days: ['Monday', 'Wednesday', 'Friday'],
            budget_range: '60-80 per hour'
          }
        }

      case 'session':
        return {
          subject: 'Mathematics',
          topic: 'Calculus Integration',
          date: '2024-12-20',
          time: '14:00',
          duration: 2.0,
          is_recurring: false
        }

      default:
        throw new Error(`Unknown test data type: ${type}`)
    }
  }
}

// Export singleton instance
module.exports = new TestHelpers()
