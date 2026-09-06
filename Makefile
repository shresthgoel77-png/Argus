.PHONY: db-up dev-backend dev-frontend

db-up:
	docker compose up -d postgres

dev-backend:
	cd backend && uvicorn app.main:app --reload

dev-frontend:
	cd frontend && npm run dev
