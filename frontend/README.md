# Frontend SPA (React/Vite/TypeScript)

This service is a Single Page Application (SPA) built with React (using Vite and TypeScript) to provide a user interface for searching and viewing property listings.

**Note: The initial project scaffolding for this service was done manually due to limitations with `npm` in the development environment. It relies on Docker for dependency installation and building.**

## Functionality

- Provides a user interface with search filters (location, price, etc.).
- Displays property listings in a card format.
- Communicates with the `backend_api_service` to fetch data.
- Implements basic pagination for search results.

## Running

This service starts automatically as part of `docker-compose up`. The frontend will be available at `http://localhost:3000`.

To view logs (Nginx logs, and build logs during `docker-compose up --build`):
```bash
docker-compose logs -f frontend_service
```

### Local Development (outside main Docker Compose, if desired)

If you wish to run the Vite development server directly for faster frontend iteration:
1.  Ensure you have Node.js and npm/yarn installed on your host machine.
2.  Navigate to the `frontend` directory: `cd frontend`
3.  Install dependencies: `npm install` (or `yarn install`)
4.  Start the dev server: `npm run dev` (or `yarn dev`)
The application will typically be available at `http://localhost:5173` (Vite's default) or another port if 5173 is busy.
Note: Ensure your backend API (`backend_api_service`) is running and accessible. The `vite.config.ts` includes a proxy setup for `/api` to `http://localhost:8000` which helps during development. If not using the proxy, ensure `VITE_API_BASE_URL` in `.env.development` or similar is set correctly.
