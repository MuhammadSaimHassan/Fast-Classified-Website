// Test setup for backend API tests
const { app } = require('../main')
const testHelpers = require('../../tests/utils/test-helpers')

beforeAll(async () => {
  // Ensure database is set up for testing
  // This would typically involve setting up a test database
  console.log('Setting up test environment...')
})

afterAll(async () => {
  // Cleanup test data
  await testHelpers.cleanupTestData()
  console.log('Test environment cleaned up')
})

beforeEach(() => {
  // Reset test helpers state
  testHelpers.reset()
})

// Global test utilities
global.testHelpers = testHelpers
global.request = require('supertest')(app)
