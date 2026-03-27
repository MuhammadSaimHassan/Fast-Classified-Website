// Test configuration for Fast Classified
module.exports = {
  // Test environment settings
  environment: {
    backendUrl: process.env.TEST_BACKEND_URL || 'http://localhost:8000',
    frontendUrl: process.env.TEST_FRONTEND_URL || 'http://localhost:5173',
    testDatabaseUrl: process.env.TEST_DATABASE_URL || 'postgresql://test:test@localhost/fastclassified_test'
  },

  // Test data settings
  data: {
    defaultPassword: 'testpass123',
    emailDomain: '@example.com',
    cleanupEnabled: true
  },

  // Test timeouts (in milliseconds)
  timeouts: {
    api: 10000,
    e2e: 30000,
    pageLoad: 15000,
    elementWait: 10000
  },

  // Test user roles and permissions
  roles: {
    student: 'student',
    teacher: 'teacher',
    admin: 'admin'
  },

  // Payment test settings
  payment: {
    providers: ['jazzcash', 'easypaisa'],
    testAmounts: [100, 500, 1000],
    currency: 'PKR'
  },

  // Browser settings for E2E tests
  browser: {
    viewportWidth: 1280,
    viewportHeight: 720,
    defaultCommandTimeout: 10000,
    requestTimeout: 15000,
    responseTimeout: 15000
  },

  // Test data generation settings
  generation: {
    maxTestUsers: 50,
    maxTestSessions: 20,
    defaultTeacherRate: 50.0,
    defaultSessionDuration: 1.5
  },

  // Reporting settings
  reporting: {
    screenshotsOnFailure: true,
    videoRecording: false,
    coverageEnabled: true,
    coverageDirectory: 'coverage'
  }
}
