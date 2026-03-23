from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "LaborTrackIQ API"
    database_url: str = "sqlite:///./labortrackiq.db"
    api_prefix: str = "/api"
    secret_key: str = "labortrackiq-dev-secret"


settings = Settings()
