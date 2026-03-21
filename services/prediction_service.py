"""
Service layer for match prediction and analysis
Wraps prediction.py and v1.py functionality with automated file handling
"""
import os
import glob
from typing import Optional, Dict, Any
import logging

# Import the prediction modules
import prediction
import v1
from app_config import settings
from services.cache_service import CacheService
from services.response_transformer import transform_analysis

logger = logging.getLogger(__name__)


class PredictionService:
    """Service for match prediction and analysis"""
    
    def __init__(self, output_dir: str = "output", cache_service: Optional[CacheService] = None):
        """
        Initialize the prediction service
        
        Args:
            output_dir: Directory where MD files are stored
            cache_service: Optional cache service instance
        """
        self.output_dir = output_dir
        self.cache_service = cache_service
        
    def _find_md_file_for_fixture(self, fixture_id: int) -> Optional[str]:
        """
        Find the MD file for a given fixture ID
        
        Args:
            fixture_id: Fixture ID to search for
            
        Returns:
            Path to MD file or None if not found
        """
        # Search in output directory
        pattern = f"{self.output_dir}/match_{fixture_id}_*.md"
        files = glob.glob(pattern)
        
        if files:
            # Return the most recent file if multiple exist
            return max(files, key=os.path.getctime)
        
        # Also search in root directory
        pattern = f"*_{fixture_id}_*.md"
        files = glob.glob(pattern)
        
        if files:
            return max(files, key=os.path.getctime)
        
        # Search for any MD file containing the fixture ID
        all_md_files = glob.glob(f"{self.output_dir}/*.md") + glob.glob("*.md")
        for file in all_md_files:
            if str(fixture_id) in file:
                return file
        
        return None
    
    def _get_latest_md_file(self) -> Optional[str]:
        """
        Get the most recently created MD file
        
        Returns:
            Path to latest MD file or None
        """
        md_files = glob.glob(f"{self.output_dir}/*.md") + glob.glob("*.md")
        
        if not md_files:
            return None
        
        return max(md_files, key=os.path.getctime)
    
    async def analyze_match_enhanced(
        self,
        md_file_path: Optional[str] = None,
        fixture_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform enhanced analysis with psychological factors (prediction.py)
        
        Args:
            md_file_path: Path to MD file (optional if fixture_id provided)
            fixture_id: Fixture ID to find MD file for (optional if md_file_path provided)
            
        Returns:
            Dictionary with analysis results
        """
        # Determine MD file path
        if not md_file_path:
            if fixture_id:
                md_file_path = self._find_md_file_for_fixture(fixture_id)
                if not md_file_path:
                    return {
                        "success": False,
                        "error": f"No MD file found for fixture {fixture_id}"
                    }
            else:
                md_file_path = self._get_latest_md_file()
                if not md_file_path:
                    return {
                        "success": False,
                        "error": "No MD files found"
                    }
        
        # Verify file exists
        if not os.path.exists(md_file_path):
            return {
                "success": False,
                "error": f"MD file not found: {md_file_path}"
            }

        # Set/validate Groq API key for llm_client
        if not settings.groq_api_key:
            return {
                "success": False,
                "error": "GROQ_API_KEY not configured"
            }
        
        try:
            # Process the match file
            logger.info(f"Processing enhanced analysis for: {md_file_path}")
            output_file = await prediction.process_match_file(
                md_file_path=md_file_path,
                output_dir=self.output_dir
            )
            
            if output_file:
                # Extract match info for response
                md_content = prediction.load_md_file(md_file_path)
                match_info = prediction.extract_complete_match_info(md_content) if md_content else None

                # Read analysis content
                analysis_content = ""
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        analysis_content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read analysis file: {e}")

                # Create summary (first 500 chars for bots)
                analysis_summary = analysis_content[:500] + "..." if len(analysis_content) > 500 else analysis_content

                return {
                    "success": True,
                    "message": "Enhanced analysis completed successfully",
                    "md_file": md_file_path,
                    "analysis_file": output_file,
                    "analysis": analysis_content,
                    "analysis_summary": analysis_summary,
                    "analysis_type": "enhanced",
                    "home_team": match_info.home_team if match_info else None,
                    "away_team": match_info.away_team if match_info else None,
                    "league": match_info.league if match_info else None,
                    "fixture_id": fixture_id
                }
            else:
                return {
                    "success": False,
                    "error": "Analysis processing failed"
                }
                
        except Exception as e:
            logger.error(f"Error in enhanced analysis: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    async def analyze_match_basic(
        self,
        md_file_path: Optional[str] = None,
        fixture_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform basic analysis (v1.py)

        Args:
            md_file_path: Path to MD file (optional if fixture_id provided)
            fixture_id: Fixture ID to find MD file for (optional if md_file_path provided)

        Returns:
            Dictionary with analysis results
        """
        # Determine MD file path
        if not md_file_path:
            if fixture_id:
                md_file_path = self._find_md_file_for_fixture(fixture_id)
                if not md_file_path:
                    return {
                        "success": False,
                        "error": f"No MD file found for fixture {fixture_id}"
                    }
            else:
                md_file_path = self._get_latest_md_file()
                if not md_file_path:
                    return {
                        "success": False,
                        "error": "No MD files found"
                    }

        # Verify file exists
        if not os.path.exists(md_file_path):
            return {
                "success": False,
                "error": f"MD file not found: {md_file_path}"
            }

        # Set/validate Groq API key for llm_client
        if not settings.groq_api_key:
            return {
                "success": False,
                "error": "GROQ_API_KEY not configured"
            }

        try:
            # Process the match file
            logger.info(f"Processing basic analysis for: {md_file_path}")
            output_file = await v1.process_md_files(
                md_file_path=md_file_path,
                output_dir=self.output_dir
            )

            if output_file:
                # Extract match info for response
                md_content = v1.load_md_file(md_file_path)
                match_info = v1.extract_match_info(md_content) if md_content else None

                # Read analysis content
                analysis_content = ""
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        analysis_content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read analysis file: {e}")

                # Create summary
                analysis_summary = analysis_content[:500] + "..." if len(analysis_content) > 500 else analysis_content

                return {
                    "success": True,
                    "message": "Basic analysis completed successfully",
                    "md_file": md_file_path,
                    "analysis_file": output_file,
                    "analysis": analysis_content,
                    "analysis_summary": analysis_summary,
                    "analysis_type": "basic",
                    "home_team": match_info.get("home_team") if match_info else None,
                    "away_team": match_info.get("away_team") if match_info else None,
                    "league": match_info.get("league") if match_info else None,
                    "fixture_id": fixture_id
                }
            else:
                return {
                    "success": False,
                    "error": "Analysis processing failed"
                }

        except Exception as e:
            logger.error(f"Error in basic analysis: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    async def analyze_match(
        self,
        md_file_path: Optional[str] = None,
        fixture_id: Optional[int] = None,
        analysis_type: str = "enhanced",
        force_refresh: bool = False,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Perform match analysis (routes to basic or enhanced)
        
        Checks cache first (unless force_refresh=True), then generates if needed.
        If only md_file_path is provided, extracts fixture_id from MD file for caching.

        Args:
            md_file_path: Path to MD file
            fixture_id: Fixture ID (will be extracted from MD file if not provided)
            analysis_type: Type of analysis ('basic' or 'enhanced')
            force_refresh: If True, bypass cache and regenerate
            use_cache: If False, skip cache entirely (default: True)

        Returns:
            Dictionary with analysis results (includes 'cached' field if from cache)
        """
        # Extract fixture_id from MD file if not provided but md_file_path is
        if not fixture_id and md_file_path and os.path.exists(md_file_path):
            try:
                # Try to extract from MD file content
                import re
                with open(md_file_path, 'r', encoding='utf-8') as f:
                    md_content = f.read()
                
                # Try to extract Match ID (which is usually the fixture_id)
                match_id_match = re.search(r'\*Match ID:\s*(\d+)\*', md_content)
                if match_id_match:
                    fixture_id = int(match_id_match.group(1))
                    logger.info(f"Extracted fixture_id {fixture_id} from MD file {md_file_path}")
                
                # Also try to extract from filename pattern: match_{fixture_id}_*.md
                if not fixture_id:
                    filename = os.path.basename(md_file_path)
                    filename_match = re.search(r'match_(\d+)_', filename)
                    if filename_match:
                        fixture_id = int(filename_match.group(1))
                        logger.info(f"Extracted fixture_id {fixture_id} from filename {filename}")
            except Exception as e:
                logger.warning(f"Could not extract fixture_id from MD file {md_file_path}: {e}")
        
        # Check cache first (if enabled and not forcing refresh)
        if self.cache_service and use_cache and not force_refresh and fixture_id:
            cached_data = self.cache_service.get_cached_analysis(fixture_id, analysis_type)
            if cached_data:
                logger.info(f"Returning cached analysis for fixture {fixture_id} ({analysis_type})")
                return {
                    "success": True,
                    "cached": True,
                    "message": "Analysis retrieved from cache",
                    "analysis_type": analysis_type,
                    "fixture_id": fixture_id,
                    "cached_data": cached_data  # Frontend-ready JSON
                }
        
        # Generate new analysis
        if analysis_type.lower() == "basic":
            result = await self.analyze_match_basic(md_file_path, fixture_id)
        else:
            result = await self.analyze_match_enhanced(md_file_path, fixture_id)
        
        # Save to cache if successful and cache service available
        if result.get("success") and self.cache_service and fixture_id and use_cache:
            try:
                # Transform analysis to frontend-ready JSON format
                analysis_text = result.get("analysis", "")
                analysis_file = result.get("analysis_file")
                transformed = transform_analysis(analysis_text, analysis_file)
                
                # Get match info for the response
                home_team = result.get("home_team", "Unknown")
                away_team = result.get("away_team", "Unknown")
                match_str = f"{home_team} vs {away_team}"
                
                # Build frontend-ready JSON (MessagingAnalysisResponse format)
                frontend_data = {
                    "success": True,
                    "fixture_id": fixture_id,
                    "match": match_str,
                    "probabilities": transformed["probabilities"],
                    "top_bets": transformed["top_bets"],
                    "summary": transformed["summary"],
                    "reasoning": transformed.get("reasoning")
                }
                
                # Extract match date if available (avoid forcing today's date).
                match_date = None
                if md_file_path and os.path.exists(md_file_path):
                    try:
                        import re

                        with open(md_file_path, "r", encoding="utf-8") as f:
                            md_text = f.read()

                        date_match = re.search(r"\*\*Date:\*\*\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", md_text)
                        if date_match:
                            match_date = date_match.group(1)
                        else:
                            # Fallback to filename token e.g. match_12345_20251224_120001.md
                            file_name = os.path.basename(md_file_path)
                            file_match = re.search(r"_(\d{8})_", file_name)
                            if file_match:
                                raw = file_match.group(1)
                                match_date = f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
                    except Exception as e:
                        logger.debug(f"Could not parse match date from {md_file_path}: {e}")
                
                # Save to cache
                self.cache_service.save_cached_analysis(
                    fixture_id=fixture_id,
                    analysis_type=analysis_type,
                    data=frontend_data,
                    match_date=match_date
                )
                logger.info(f"Cached analysis for fixture {fixture_id} ({analysis_type})")
                
            except Exception as e:
                logger.error(f"Error saving to cache for fixture {fixture_id}: {e}")
                # Don't fail the request if cache save fails
        
        result["cached"] = False
        return result
