from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "LaborTrackIQ API"
    database_url: str = "sqlite:///./labortrackiq.db"
    api_prefix: str = "/api"
    secret_key: str = "labortrackiq-dev-secret"
    quickbooks_client_id: str = ""
    quickbooks_client_secret: str = ""
    quickbooks_redirect_uri: str = "http://127.0.0.1:8000/api/integrations/quickbooks/callback"
    quickbooks_environment: str = "sandbox"
    quickbooks_scopes: str = "com.intuit.quickbooks.accounting"


settings = Settings()
