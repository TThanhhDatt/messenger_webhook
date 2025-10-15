import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.routes import router as api_router_v1

app = FastAPI(
    title="Messenger webhook",
    # lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allows all headers
)

app.include_router(api_router_v1)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)