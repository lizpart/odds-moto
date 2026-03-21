"""
Services package for Football Analysis API
"""
from .data_collection_service import DataCollectionService
from .prediction_service import PredictionService

__all__ = ["DataCollectionService", "PredictionService"]

