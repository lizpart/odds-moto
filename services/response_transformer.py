"""
Response transformation utilities for converting verbose API responses
into clean, minimal structures optimized for messaging apps (WhatsApp/Telegram)
"""
import re
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


def transform_fixture_data(fixture_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform verbose fixture data into minimal structure for messaging apps.
    
    Args:
        fixture_data: Raw fixture data from API-Football (can be from get_fixtures or get_match_context)
        
    Returns:
        Clean fixture object with only essential fields
    """
    try:
        # Handle different data structures:
        # 1. From get_match_context: {"api_data": {"fixture": {...}}}
        # 2. From get_fixtures: {"fixture": {...}, "teams": {...}, "league": {...}}
        # 3. Direct API-Football response format
        
        fixture = None
        teams = None
        league = None
        
        # Case 1: Nested structure from get_match_context
        if "api_data" in fixture_data:
            api_data = fixture_data.get("api_data", {})
            if isinstance(api_data, dict):
                # Could be a list of fixtures or a single fixture dict
                if "fixture" in api_data:
                    fixture = api_data.get("fixture", {})
                elif isinstance(api_data, dict) and "response" in api_data:
                    # API-Football response format
                    response = api_data.get("response", [])
                    if response and len(response) > 0:
                        fixture = response[0]
        
        # Case 2: Direct API-Football fixture format
        if not fixture:
            if "fixture" in fixture_data:
                fixture = fixture_data
            else:
                fixture = fixture_data
        
        # Extract fixture details
        fixture_info = fixture.get("fixture", {}) if isinstance(fixture, dict) and "fixture" in fixture else fixture
        teams = fixture.get("teams", {}) if isinstance(fixture, dict) and "teams" in fixture else teams or {}
        league = fixture.get("league", {}) if isinstance(fixture, dict) and "league" in fixture else league or {}
        
        # Extract essential fields
        fixture_id = fixture_info.get("id") if isinstance(fixture_info, dict) else None
        date = fixture_info.get("date", "") if isinstance(fixture_info, dict) else ""
        
        # Extract status
        status = "NS"
        if isinstance(fixture_info, dict):
            status_obj = fixture_info.get("status", {})
            if isinstance(status_obj, dict):
                status = status_obj.get("short", status_obj.get("long", "NS"))
        
        # Extract team names
        home_team = "Unknown"
        away_team = "Unknown"
        if isinstance(teams, dict):
            home_team = teams.get("home", {}).get("name", "Unknown") if isinstance(teams.get("home"), dict) else "Unknown"
            away_team = teams.get("away", {}).get("name", "Unknown") if isinstance(teams.get("away"), dict) else "Unknown"
        
        # Extract league name
        league_name = "Unknown League"
        if isinstance(league, dict):
            league_name = league.get("name", "Unknown League")
        
        # Format time from date string (YYYY-MM-DDTHH:MM:SS+00:00)
        time_str = "TBD"
        date_str = ""
        if date:
            try:
                # Extract date part
                if "T" in date:
                    date_str = date.split("T")[0]
                    # Extract time part
                    time_part = date.split("T")[1].split("+")[0].split(":")[:2]
                    time_str = ":".join(time_part)
                else:
                    date_str = date
            except:
                date_str = date if date else ""
        
        return {
            "id": fixture_id,
            "match": f"{home_team} vs {away_team}",
            "home_team": home_team,
            "away_team": away_team,
            "time": time_str,
            "date": date_str,
            "league": league_name,
            "status": status
        }
    except Exception as e:
        logger.error(f"Error transforming fixture data: {e}")
        return {
            "id": None,
            "match": "Unknown vs Unknown",
            "home_team": "Unknown",
            "away_team": "Unknown",
            "time": "TBD",
            "date": "",
            "league": "Unknown League",
            "status": "NS"
        }


def transform_analysis(analysis_text: str, md_file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse analysis text (from MD file) and extract key predictions for messaging apps.
    
    Args:
        analysis_text: Full analysis text content
        md_file_path: Optional path to MD file (for fallback)
        
    Returns:
        Clean analysis object with probabilities, top bets, and summary
    """
    try:
        result = {
            "probabilities": {"home": 0, "draw": 0, "away": 0},
            "top_bets": [],
            "summary": "",
            "reasoning": ""
        }
        
        if not analysis_text:
            return result
        
        # Extract win probabilities
        prob_pattern = r'WIN PROBABILITY:\s*Home\s*(\d+)%\s*\|\s*Draw\s*(\d+)%\s*\|\s*Away\s*(\d+)%'
        prob_match = re.search(prob_pattern, analysis_text, re.IGNORECASE)
        if prob_match:
            result["probabilities"] = {
                "home": int(prob_match.group(1)),
                "draw": int(prob_match.group(2)),
                "away": int(prob_match.group(3))
            }
        
        # Extract recommended bets
        bets_section = ""
        if "RECOMMENDED BETS" in analysis_text:
            bets_start = analysis_text.find("RECOMMENDED BETS")
            reasoning_start = analysis_text.find("REASONING:", bets_start)
            if reasoning_start > bets_start:
                bets_section = analysis_text[bets_start:reasoning_start]
            else:
                bets_section = analysis_text[bets_start:bets_start + 500]
        
        # Extract individual bets (format: "- [Bet Description] @ [Odds]")
        bet_pattern = r'-\s+([^@]+?)\s+@\s+([\d.]+)'
        bet_matches = re.findall(bet_pattern, bets_section)
        
        top_bets = []
        for bet_desc, odds in bet_matches[:5]:  # Top 5 bets
            top_bets.append({
                "bet": bet_desc.strip(),
                "odds": float(odds)
            })
        
        result["top_bets"] = top_bets
        
        # Extract reasoning
        if "REASONING:" in analysis_text:
            reasoning_start = analysis_text.find("REASONING:")
            reasoning_text = analysis_text[reasoning_start + len("REASONING:"):].strip()
            # Take first 300 chars for summary
            result["reasoning"] = reasoning_text[:500] + "..." if len(reasoning_text) > 500 else reasoning_text
            result["summary"] = reasoning_text[:200] + "..." if len(reasoning_text) > 200 else reasoning_text
        else:
            # Fallback: use first 200 chars of analysis
            result["summary"] = analysis_text[:200] + "..." if len(analysis_text) > 200 else analysis_text
        
        return result
        
    except Exception as e:
        logger.error(f"Error transforming analysis: {e}")
        return {
            "probabilities": {"home": 33, "draw": 34, "away": 33},
            "top_bets": [],
            "summary": "Analysis parsing failed",
            "reasoning": ""
        }


def transform_team_stats(team_data: Dict[str, Any], team_name: str) -> Dict[str, Any]:
    """
    Extract team statistics summary for messaging apps.
    
    Args:
        team_data: Raw team statistics data
        team_name: Name of the team
        
    Returns:
        Clean team stats object
    """
    try:
        result = {
            "team": team_name,
            "position": None,
            "form": "",
            "goals_scored": 0,
            "goals_conceded": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0
        }
        
        # Extract from standings if available
        if "standings" in team_data:
            standings = team_data.get("standings", [])
            if standings and len(standings) > 0:
                for group in standings:
                    if isinstance(group, dict) and "group" in group:
                        teams = group.get("group", [])
                        for team in teams:
                            if isinstance(team, dict) and team.get("team", {}).get("name") == team_name:
                                result["position"] = team.get("rank")
                                result["goals_scored"] = team.get("goals", {}).get("for", 0)
                                result["goals_conceded"] = team.get("goals", {}).get("against", 0)
                                result["wins"] = team.get("all", {}).get("win", 0)
                                result["draws"] = team.get("all", {}).get("draw", 0)
                                result["losses"] = team.get("all", {}).get("lose", 0)
                                break
        
        # Extract form from recent fixtures
        if "form" in team_data:
            result["form"] = team_data.get("form", "")
        elif "recent_form" in team_data:
            result["form"] = team_data.get("recent_form", "")
        
        return result
        
    except Exception as e:
        logger.error(f"Error transforming team stats: {e}")
        return {
            "team": team_name,
            "position": None,
            "form": "",
            "goals_scored": 0,
            "goals_conceded": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0
        }

