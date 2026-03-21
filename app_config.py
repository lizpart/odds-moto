"""
Configuration management for the Football Analysis API
Loads settings from config.json and environment variables
"""
import os
import json
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # API Keys
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    api_football_key: str = Field(default="", env="API_FOOTBALL_KEY")
    serper_api_key: str = Field(default="", env="SERPER_API_KEY")

    # LLM (Groq/OpenAI-compatible deepseek models)
    groq_api_key: str = Field(default="", env="GROQ_API_KEY")
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        env="GROQ_BASE_URL",
    )
    groq_model: str = Field(default="deepseek-r1-distill-llama-70b", env="GROQ_MODEL")
    
    # Server settings
    # Use 127.0.0.1 instead of 0.0.0.0 for better Windows compatibility
    host: str = Field(default="127.0.0.1", env="HOST")
    port: int = Field(default=8000, env="PORT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Directories
    output_dir: str = Field(default="output", env="OUTPUT_DIR")
    cache_dir: str = Field(default="cache", env="CACHE_DIR")
    db_path: str = Field(default="data/football.db", env="DB_PATH")
    auto_migrate_legacy: bool = Field(default=True, env="AUTO_MIGRATE_LEGACY")
    
    # Cache settings
    cache_enabled: bool = Field(default=True, env="CACHE_ENABLED")
    cache_ttl_hours: int = Field(default=24, env="CACHE_TTL_HOURS")
    
    # Config file path
    config_file: str = Field(default="config.json", env="CONFIG_FILE")

    @field_validator("debug", mode="before")
    @classmethod
    def _coerce_debug(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return value
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


def load_config(config_path: str = "config.json") -> dict:
    """
    Load configuration from JSON file
    
    Args:
        config_path: Path to config.json file
        
    Returns:
        Configuration dictionary
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Config file {config_path} not found. Using defaults.")
        return {}
    except json.JSONDecodeError as e:
        print(f"Error parsing config file: {e}")
        return {}


def get_settings() -> Settings:
    """Get application settings singleton"""
    return Settings()


def get_openai_key(settings: Optional[Settings] = None, config: Optional[dict] = None) -> str:
    """
    Get OpenAI API key from settings or config
    Priority: Environment variable > .env > Config file
    
    Returns:
        API key string, empty if not found
    """
    # Check environment variable directly first
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key and env_key.strip():
        # Basic validation - ensure it's not a placeholder
        if env_key.strip() not in ["YOUR_OPENAI_API_KEY_HERE", "PLACEHOLDER"]:
            return env_key.strip()

    # Check settings (from .env file via pydantic)
    if settings and settings.openai_api_key and settings.openai_api_key.strip():
        key = settings.openai_api_key.strip()
        if key not in ["YOUR_OPENAI_API_KEY_HERE", "PLACEHOLDER"]:
            return key

    # Fallback to config.json file
    if config:
        key = config.get("openai_api_key", "")
        if key and key.strip() and key not in ["YOUR_OPENAI_API_KEY_HERE", "PLACEHOLDER"]:
            return key.strip()

    return ""


def get_api_football_key(settings: Optional[Settings] = None, config: Optional[dict] = None) -> str:
    """
    Get API-Football key from settings or config
    Priority: Environment variable > Settings > Config file
    """
    if settings and settings.api_football_key:
        return settings.api_football_key
    
    # Check config file
    if config and "api_football" in config:
        return config["api_football"].get("api_key", "")
    
    return ""


def get_serper_key(settings: Optional[Settings] = None, config: Optional[dict] = None) -> str:
    """
    Get Serper API key from settings or config
    Priority: Environment variable > Settings > Config file
    """
    if settings and settings.serper_api_key:
        return settings.serper_api_key
    
    # Check config file
    if config and "serper" in config:
        return config["serper"].get("api_key", "")
    
    return ""


# Global settings instance
settings = get_settings()
config = load_config(settings.config_file)
