# Frontend (React + TypeScript)

This directory contains the React + TypeScript frontend for the Test Orchestration platform. It provides the user interface for interacting with test suites, viewing execution history, managing schedules, and user authentication.

## Key Features Handled by Frontend
- User registration and login.
- Displaying available test suites based on product selection.
- Dynamically rendering input forms for test suites from configuration.
- Starting test suite executions.
- Listing and viewing details of workflow executions, including event history.
- Creating, listing, and deleting test execution schedules.
- Role-based access control for UI elements and actions.

## Tech Stack
- **React**: JavaScript library for building user interfaces.
- **TypeScript**: Superset of JavaScript adding static typing.
- **Axios**: Promise-based HTTP client for API communication.
- **React Router**: For client-side routing and navigation.
- **React Context API**: For global state management (e.g., authentication).
- **CSS**: For styling (basic CSS, can be extended with modules or CSS-in-JS).

## Running Locally (Standalone Development)

This is for developing the frontend independently of the Docker Compose setup. Ensure the backend API is running and accessible.

1.  **Navigate to the `frontend` directory**:
    ```bash
    cd frontend
    ```
2.  **Install dependencies**:
    It's recommended to use `yarn` if `yarn.lock` is present, otherwise `npm`.
    ```bash
    yarn install
    # OR
    # npm install
    ```
3.  **Set Environment Variables**:
    The primary environment variable needed is `REACT_APP_API_BASE_URL`. Create a `.env` file in the `frontend` directory (e.g., `frontend/.env`):
    ```env
    REACT_APP_API_BASE_URL=http://localhost:8000
    ```
    This should point to where your backend API is running (port 8000 if following the backend setup).

4.  **Start the development server**:
    ```bash
    yarn start
    # OR
    # npm start
    ```
    The application will typically open in your browser at `http://localhost:3000`.

## Building for Production
To create an optimized production build:
```bash
yarn build
# OR
# npm run build
```
The build artifacts will be in the `build/` directory. The `frontend/Dockerfile` uses this command to build the image.

## API Interaction
The frontend interacts with the backend API. The base URL is configured via the `REACT_APP_API_BASE_URL` environment variable. All API communication is handled through the `src/services/apiService.ts` module.

## Testing Strategy Notes
- **Unit/Component Tests**: Use Jest and React Testing Library (`@testing-library/react`) for testing individual components (e.g., `DynamicForm`, form validation, context providers) and utility functions.
  - Run tests: `yarn test` or `npm test`.
- **End-to-End (E2E) Tests**: Consider using tools like Cypress or Playwright to test user flows such as login, test execution submission, schedule creation, and navigation. E2E tests would typically run against a fully running application stack (e.g., via `docker-compose`).

Refer to the main project README's "Testing Strategy" section for a more comprehensive overview.
