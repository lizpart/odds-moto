import os
import asyncio
import re
import json
from datetime import datetime
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from llm_client import call_llm

# === Data Classes ===
@dataclass
class PlayerPsychologicalState:
    """Represents a player's psychological state and welfare"""
    name: str
    issues: List[str] = field(default_factory=list)
    sentiment_score: float = 0.0  # -1.0 (very negative) to 1.0 (very positive)
    impact_level: str = "low"  # low, medium, high, critical
    is_key_player: bool = False
    
    def calculate_performance_modifier(self) -> float:
        """Calculate how much this affects performance (0.0 to 1.0, where 1.0 is no impact)"""
        base_impact = {
            "low": 0.95,
            "medium": 0.85,
            "high": 0.70,
            "critical": 0.50
        }
        
        modifier = base_impact.get(self.impact_level, 0.90)
        
        # Adjust based on sentiment
        sentiment_adjustment = self.sentiment_score * 0.15
        modifier += sentiment_adjustment
        
        # Key players have larger impact when affected
        if self.is_key_player:
            modifier = modifier * 0.85 + 0.15  # Slightly worse impact
        
        return max(0.3, min(1.0, modifier))


@dataclass
class TeamPsychologicalProfile:
    """Represents a team's overall psychological state"""
    team_name: str
    affected_players: List[PlayerPsychologicalState] = field(default_factory=list)
    team_news: List[str] = field(default_factory=list)
    injuries: List[Dict[str, str]] = field(default_factory=list)
    morale_score: float = 0.5  # 0.0 (very low) to 1.0 (very high)
    recent_controversy: bool = False
    fan_sentiment: str = "neutral"  # positive, neutral, negative
    
    def calculate_team_performance_modifier(self) -> float:
        """Calculate overall team performance modifier"""
        if not self.affected_players:
            base_modifier = 0.95
        else:
            # Average performance impact from affected players
            player_impacts = [p.calculate_performance_modifier() for p in self.affected_players]
            avg_player_impact = sum(player_impacts) / len(player_impacts)
            
            # Weight key players more heavily
            key_player_impacts = [p.calculate_performance_modifier() 
                                for p in self.affected_players if p.is_key_player]
            
            if key_player_impacts:
                key_avg = sum(key_player_impacts) / len(key_player_impacts)
                base_modifier = (avg_player_impact * 0.4 + key_avg * 0.6)
            else:
                base_modifier = avg_player_impact
        
        # Factor in morale
        morale_impact = (self.morale_score - 0.5) * 0.2
        base_modifier += morale_impact
        
        # Fan sentiment impact
        fan_impact = {
            "positive": 0.05,
            "neutral": 0.0,
            "negative": -0.08
        }
        base_modifier += fan_impact.get(self.fan_sentiment, 0.0)
        
        # Recent controversy
        if self.recent_controversy:
            base_modifier -= 0.07
        
        # Injury impact (each injury reduces performance)
        injury_impact = min(0.15, len(self.injuries) * 0.03)
        base_modifier -= injury_impact
        
        return max(0.4, min(1.0, base_modifier))


@dataclass
class MatchInfo:
    """Enhanced match information structure"""
    match_id: str
    venue: str
    date: str
    home_team: str
    away_team: str
    league: str
    raw_content: str
    scraped_odds: Optional[Dict[str, float]] = None
    home_team_profile: Optional[TeamPsychologicalProfile] = None
    away_team_profile: Optional[TeamPsychologicalProfile] = None
    stats: Dict = field(default_factory=dict)


# === File Operations ===
def load_md_file(file_path: str) -> Optional[str]:
    """Loads content from a Markdown file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return None


# === Enhanced Extraction Functions ===
def extract_basic_match_info(md_content: str) -> Dict:
    """Extracts basic match details from the Markdown content."""
    if md_content is None:
        return None

    match_id_match = re.search(r'\*Match ID: ([^*]+)\*', md_content)
    match_id = match_id_match.group(1).strip() if match_id_match else "Unknown_ID"

    venue_match = re.search(r'\*Venue: ([^*]+)\*', md_content)
    venue = venue_match.group(1).strip() if venue_match else "Unknown Venue"

    date_match = re.search(r'\*Date: ([^*]+)\*', md_content)
    date = date_match.group(1).strip() if date_match else "Unknown Date"

    title_match = re.search(r'^#\s*([^#\n]+)\s+vs\s+([^#\n]+)', md_content, re.IGNORECASE | re.MULTILINE)
    if title_match:
        home_team = title_match.group(1).strip()
        away_team = title_match.group(2).strip()
    else:
        alt_title_match = re.search(r'([^#\n]+)\s+vs\s+([^#\n]+)', md_content, re.IGNORECASE)
        if alt_title_match:
            home_team = alt_title_match.group(1).strip()
            away_team = alt_title_match.group(2).strip()
        else:
            home_team = "Unknown Home Team"
            away_team = "Unknown Away Team"

    league_match = re.search(r'\*League: ([^*]+)\*', md_content)
    league = league_match.group(1).strip() if league_match else "Unknown League"

    return {
        "match_id": match_id,
        "venue": venue,
        "date": date,
        "home_team": home_team,
        "away_team": away_team,
        "league": league,
        "raw_content": md_content
    }


def extract_scraped_odds(md_content: str) -> Optional[Dict[str, float]]:
    """Extract odds that were scraped and included in the MD file"""
    odds = {}
    
    # Look for various odds patterns
    patterns = {
        'home_win': r'(?:Home Win|1X2.*Home)[\s:]+(\d+\.?\d*)',
        'draw': r'(?:Draw|1X2.*Draw)[\s:]+(\d+\.?\d*)',
        'away_win': r'(?:Away Win|1X2.*Away)[\s:]+(\d+\.?\d*)',
        'over_2_5': r'Over 2\.5[\s:]+(\d+\.?\d*)',
        'under_2_5': r'Under 2\.5[\s:]+(\d+\.?\d*)',
        'btts_yes': r'(?:BTTS|Both Teams to Score)[\s:]+Yes[\s:]+(\d+\.?\d*)',
        'btts_no': r'(?:BTTS|Both Teams to Score)[\s:]+No[\s:]+(\d+\.?\d*)',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, md_content, re.IGNORECASE)
        if match:
            try:
                odds[key] = float(match.group(1))
            except ValueError:
                continue
    
    return odds if odds else None


def extract_player_psychological_factors(md_content: str, team_name: str) -> List[PlayerPsychologicalState]:
    """Extract psychological factors affecting individual players"""
    players = []
    
    # Define patterns for psychological issues
    issue_patterns = {
        'social_media_backlash': r'(?:' + re.escape(team_name) + r'.*?)?(\w+(?:\s+\w+)?)\s+(?:faces?|receives?|suffers?)\s+(?:social media|online|twitter|instagram)\s+(?:backlash|criticism|abuse|hate)',
        'booed': r'(\w+(?:\s+\w+)?)\s+(?:was |were |got |being )?booed',
        'personal_issues': r'(\w+(?:\s+\w+)?)\s+(?:divorce|separated|personal issues?|family (?:issues?|problems?)|loss)',
        'criticism': r'(\w+(?:\s+\w+)?)\s+(?:criticized|slammed|blasted|under fire)',
        'injury_concern': r'(\w+(?:\s+\w+)?)\s+(?:injury concern|fitness doubt|injury scare)',
        'controversy': r'(\w+(?:\s+\w+)?)\s+(?:involved in|at center of|embroiled in)\s+(?:controversy|scandal)',
        'poor_form': r'(\w+(?:\s+\w+)?)\s+(?:struggling|poor form|out of form|disappointing)',
    }
    
    for issue_type, pattern in issue_patterns.items():
        matches = re.finditer(pattern, md_content, re.IGNORECASE)
        for match in matches:
            player_name = match.group(1).strip()
            
            # Check if player already exists
            existing_player = next((p for p in players if p.name.lower() == player_name.lower()), None)
            
            if existing_player:
                if issue_type not in existing_player.issues:
                    existing_player.issues.append(issue_type)
            else:
                player = PlayerPsychologicalState(
                    name=player_name,
                    issues=[issue_type]
                )
                players.append(player)
    
    # Determine impact levels and sentiment scores
    for player in players:
        impact_score = 0
        sentiment = 0.0
        
        issue_weights = {
            'personal_issues': (3, -0.8),  # (impact, sentiment)
            'social_media_backlash': (2, -0.6),
            'booed': (2, -0.7),
            'controversy': (3, -0.75),
            'criticism': (2, -0.5),
            'poor_form': (2, -0.4),
            'injury_concern': (1, -0.3),
        }
        
        for issue in player.issues:
            weight, sent = issue_weights.get(issue, (1, -0.3))
            impact_score += weight
            sentiment += sent
        
        # Average sentiment
        player.sentiment_score = sentiment / len(player.issues) if player.issues else 0.0
        
        # Determine impact level
        if impact_score >= 6:
            player.impact_level = "critical"
        elif impact_score >= 4:
            player.impact_level = "high"
        elif impact_score >= 2:
            player.impact_level = "medium"
        else:
            player.impact_level = "low"
    
    return players


def identify_key_players(md_content: str, team_name: str, players: List[PlayerPsychologicalState]) -> None:
    """Identify which players are key players for their team"""
    key_indicators = [
        r'(?:star|key|important|crucial|main|top)\s+(?:player|striker|midfielder|defender)',
        r'(?:captain|vice-captain)',
        r'(?:leading scorer|top scorer)',
        r'(?:playmaker|talisman)',
        r'(?:best player|standout|star man)',
    ]
    
    for player in players:
        # Check if player is mentioned as key
        for indicator in key_indicators:
            # Look for patterns like "key player John Doe" or "John Doe, the key player"
            pattern = f'(?:{indicator}\\s+{re.escape(player.name)}|{re.escape(player.name)}[,\\s]+(?:the\\s+)?{indicator})'
            if re.search(pattern, md_content, re.IGNORECASE):
                player.is_key_player = True
                break


def extract_team_news(md_content: str, team_name: str) -> List[str]:
    """Extract recent news about the team"""
    news = []
    
    # Look for news sections
    news_section_pattern = rf'(?:News|Latest|Update).*?{re.escape(team_name)}.*?:(.*?)(?:\n\n|\Z)'
    news_matches = re.finditer(news_section_pattern, md_content, re.IGNORECASE | re.DOTALL)
    
    for match in news_matches:
        news_text = match.group(1).strip()
        # Split by bullet points or newlines
        news_items = re.split(r'[\n•\-*]+', news_text)
        news.extend([item.strip() for item in news_items if item.strip()])
    
    # Also look for general news mentions
    news_keywords = [
        'announces', 'confirms', 'reveals', 'statement', 'press conference',
        'manager says', 'coach says', 'reportedly', 'according to'
    ]
    
    for keyword in news_keywords:
        pattern = rf'{re.escape(team_name)}.*?{keyword}.*?([^.!?]+[.!?])'
        matches = re.finditer(pattern, md_content, re.IGNORECASE)
        for match in matches:
            news_item = match.group(1).strip()
            if news_item and news_item not in news:
                news.append(news_item)
    
    return news[:10]  # Limit to top 10 news items


def extract_injuries(md_content: str, team_name: str) -> List[Dict[str, str]]:
    """Extract injury information"""
    injuries = []
    
    injury_patterns = [
        r'(\w+(?:\s+\w+)?)\s+(?:is |will be |remains? )?(?:injured|out|sidelined|unavailable|doubtful)',
        r'(\w+(?:\s+\w+)?)\s+(?:suffered|sustained)\s+(?:a |an )?(?:injury|knock|problem)',
        r'(?:Injured|Out|Sidelined|Unavailable):\s*(\w+(?:\s+\w+)?)',
    ]
    
    for pattern in injury_patterns:
        matches = re.finditer(pattern, md_content, re.IGNORECASE)
        for match in matches:
            player_name = match.group(1).strip()
            
            # Try to extract injury type and duration
            injury_context = md_content[max(0, match.start()-100):min(len(md_content), match.end()+100)]
            
            injury_type = "Unknown"
            injury_type_match = re.search(r'(?:knee|ankle|hamstring|muscle|shoulder|back|head|thigh|calf|groin)\s+(?:injury|problem|issue)', 
                                         injury_context, re.IGNORECASE)
            if injury_type_match:
                injury_type = injury_type_match.group(0)
            
            duration = "Unknown"
            duration_match = re.search(r'(\d+)\s+(?:weeks?|months?|days?)', injury_context)
            if duration_match:
                duration = duration_match.group(0)
            
            injuries.append({
                'player': player_name,
                'type': injury_type,
                'duration': duration
            })
    
    return injuries


def analyze_fan_sentiment(md_content: str, team_name: str) -> str:
    """Analyze fan sentiment towards the team"""
    positive_indicators = [
        'excellent form', 'great performance', 'fans delighted', 'support',
        'optimistic', 'confident', 'excited', 'backing'
    ]
    
    negative_indicators = [
        'booed', 'fans angry', 'disappointed', 'frustrated', 'protest',
        'under pressure', 'criticism', 'poor form', 'struggling'
    ]
    
    positive_count = sum(1 for indicator in positive_indicators 
                        if re.search(rf'{re.escape(team_name)}.*?{indicator}', md_content, re.IGNORECASE))
    
    negative_count = sum(1 for indicator in negative_indicators 
                        if re.search(rf'{re.escape(team_name)}.*?{indicator}', md_content, re.IGNORECASE))
    
    if positive_count > negative_count + 1:
        return "positive"
    elif negative_count > positive_count + 1:
        return "negative"
    else:
        return "neutral"


def calculate_team_morale(md_content: str, team_name: str, team_news: List[str]) -> float:
    """Calculate team morale score based on recent events"""
    morale = 0.5  # Neutral starting point
    
    # Positive morale indicators
    positive_keywords = [
        'winning streak', 'victory', 'triumph', 'success', 'confident',
        'good form', 'momentum', 'unbeaten', 'impressive'
    ]
    
    # Negative morale indicators
    negative_keywords = [
        'losing', 'defeat', 'crisis', 'turmoil', 'pressure', 'struggling',
        'poor form', 'winless', 'disappointing'
    ]
    
    # Check content
    content_to_check = md_content + ' '.join(team_news)
    
    positive_score = sum(1 for keyword in positive_keywords 
                        if re.search(rf'{re.escape(team_name)}.*?{keyword}', content_to_check, re.IGNORECASE))
    
    negative_score = sum(1 for keyword in negative_keywords 
                        if re.search(rf'{re.escape(team_name)}.*?{keyword}', content_to_check, re.IGNORECASE))
    
    # Adjust morale
    morale += (positive_score * 0.08)
    morale -= (negative_score * 0.08)
    
    return max(0.0, min(1.0, morale))


def check_recent_controversy(md_content: str, team_name: str) -> bool:
    """Check if team has recent controversy"""
    controversy_keywords = [
        'controversy', 'scandal', 'investigation', 'allegations',
        'disciplinary', 'fined', 'banned', 'suspended'
    ]
    
    for keyword in controversy_keywords:
        if re.search(rf'{re.escape(team_name)}.*?{keyword}', md_content, re.IGNORECASE):
            return True
    
    return False


def build_team_psychological_profile(md_content: str, team_name: str) -> TeamPsychologicalProfile:
    """Build comprehensive psychological profile for a team"""
    # Extract player psychological factors
    affected_players = extract_player_psychological_factors(md_content, team_name)
    
    # Identify key players
    identify_key_players(md_content, team_name, affected_players)
    
    # Extract other factors
    team_news = extract_team_news(md_content, team_name)
    injuries = extract_injuries(md_content, team_name)
    fan_sentiment = analyze_fan_sentiment(md_content, team_name)
    morale_score = calculate_team_morale(md_content, team_name, team_news)
    recent_controversy = check_recent_controversy(md_content, team_name)
    
    return TeamPsychologicalProfile(
        team_name=team_name,
        affected_players=affected_players,
        team_news=team_news,
        injuries=injuries,
        morale_score=morale_score,
        recent_controversy=recent_controversy,
        fan_sentiment=fan_sentiment
    )


def extract_match_stats(md_content: str) -> Dict:
    """Extract statistical information from markdown content"""
    stats = {}
    
    patterns = {
        'home_form': r'Home Team Form:?\s*([WDLWDL\s]+)',
        'away_form': r'Away Team Form:?\s*([WDLWDL\s]+)',
        'h2h': r'Head to Head:?\s*([^\n]+)',
        'home_position': r'Home Team Position:?\s*(\d+)',
        'away_position': r'Away Team Position:?\s*(\d+)',
        'home_goals_scored': r'Home Goals Scored:?\s*(\d+)',
        'away_goals_scored': r'Away Goals Scored:?\s*(\d+)',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, md_content, re.IGNORECASE)
        if match:
            stats[key] = match.group(1).strip()
    
    return stats


def extract_complete_match_info(md_content: str) -> Optional[MatchInfo]:
    """Extract complete match information including psychological profiles"""
    basic_info = extract_basic_match_info(md_content)
    if not basic_info:
        return None
    
    # Extract scraped odds
    scraped_odds = extract_scraped_odds(md_content)
    
    # Build psychological profiles for both teams
    home_profile = build_team_psychological_profile(md_content, basic_info['home_team'])
    away_profile = build_team_psychological_profile(md_content, basic_info['away_team'])
    
    # Extract stats
    stats = extract_match_stats(md_content)
    
    return MatchInfo(
        match_id=basic_info['match_id'],
        venue=basic_info['venue'],
        date=basic_info['date'],
        home_team=basic_info['home_team'],
        away_team=basic_info['away_team'],
        league=basic_info['league'],
        raw_content=md_content,
        scraped_odds=scraped_odds,
        home_team_profile=home_profile,
        away_team_profile=away_profile,
        stats=stats
    )


# === AI Analysis Functions ===
def get_enhanced_system_prompt() -> str:
    """Returns enhanced system prompt with psychological analysis capabilities"""
    return """
You are an Elite Football Betting Prediction AI with advanced psychological analysis capabilities. 

Your unique advantage: You analyze not just statistics and form, but also psychological and contextual factors that affect player and team performance.

🎯 Your Core Competencies:
1. Statistical Analysis: Form, head-to-head, league position
2. Psychological Analysis: Player mental state, team morale, fan pressure
3. Contextual Analysis: Injuries, controversies, personal issues affecting players
4. Market Analysis: Evaluate scraped odds and identify value bets
5. Holistic Prediction: Combine all factors for accurate match predictions

📊 You will receive:
- Match details and statistics
- Psychological profiles of both teams
- Individual player psychological states and their impact levels
- Scraped odds from bookmakers (if available)
- Team news, injuries, and contextual factors

🧠 Psychological Factors to Consider:
- Key players dealing with personal issues (divorce, loss, family problems)
- Players facing social media backlash or criticism
- Players being booed by their own fans
- Team morale and fan sentiment
- Recent controversies affecting team cohesion
- Injury impact on team strategy

⚖️ Performance Modifiers:
You will receive calculated performance modifiers for each team based on psychological factors.
A modifier of 1.0 means no impact, while 0.5 means 50% reduced performance capacity.
Factor these into your predictions appropriately.

📈 Odds Analysis:
If scraped odds are provided, use them as a baseline but DO NOT blindly accept them.
Reevaluate based on psychological factors that bookmakers may have underweighted.
Identify value bets where psychological factors suggest different probabilities than market odds.

Format your response EXACTLY as follows:
MATCH: [Home Team] vs [Away Team]
PSYCHOLOGICAL IMPACT SUMMARY:
- Home Team: [Brief assessment of psychological state and key factors]
- Away Team: [Brief assessment of psychological state and key factors]

PERFORMANCE MODIFIERS:
- Home Team Modifier: [X.XX] ([percentage]% of optimal performance)
- Away Team Modifier: [X.XX] ([percentage]% of optimal performance)

ADJUSTED WIN PROBABILITY: Home XX% | Draw XX% | Away XX%

SCRAPED ODDS ANALYSIS: [If provided, compare your probabilities with market odds and identify value]

RECOMMENDED BETS (With Confidence Level):
1. [Specific Bet 1] @ [Odd] - Confidence: [High/Medium/Low] - Reasoning: [Brief explanation]
2. [Specific Bet 2] @ [Odd] - Confidence: [High/Medium/Low] - Reasoning: [Brief explanation]
3. [Specific Bet 3] @ [Odd] - Confidence: [High/Medium/Low] - Reasoning: [Brief explanation]
4. [Specific Bet 4] @ [Odd] - Confidence: [High/Medium/Low] - Reasoning: [Brief explanation]
5. [Specific Bet 5] @ [Odd] - Confidence: [High/Medium/Low] - Reasoning: [Brief explanation]
[Additional bets as appropriate]

DETAILED ANALYSIS:
[Comprehensive analysis covering:
- Statistical factors
- Psychological factors and their specific impact
- How key player issues affect team dynamics
- Tactical implications
- Why your predictions differ from or align with scraped odds]

KEY INSIGHTS:
- [Unique insight 1 about psychological factors]
- [Unique insight 2 about value opportunities]
- [Additional insights as relevant]

⚠️ Critical Requirements:
- ALWAYS incorporate psychological factors into your analysis
- Probabilities MUST sum to exactly 100%
- Provide at least 5 betting recommendations
- Explain how psychological factors influenced your predictions
- If scraped odds provided, explain any discrepancies with your assessment
- Include confidence levels for each bet
- Never use placeholders - all values must be specific and realistic
- Draw on deep football knowledge while emphasizing unique psychological insights
"""


def build_enhanced_match_prompt(match_info: MatchInfo) -> str:
    """Build comprehensive prompt with all extracted information"""
    
    # Performance modifiers
    home_modifier = match_info.home_team_profile.calculate_team_performance_modifier()
    away_modifier = match_info.away_team_profile.calculate_team_performance_modifier()
    
    prompt = f"""
=== MATCH INFORMATION ===
MATCH: {match_info.home_team} vs {match_info.away_team}
VENUE: {match_info.venue}
DATE: {match_info.date}
LEAGUE: {match_info.league}

=== PSYCHOLOGICAL ANALYSIS ===

HOME TEAM ({match_info.home_team}) PSYCHOLOGICAL PROFILE:
Performance Modifier: {home_modifier:.2f} ({home_modifier*100:.0f}% of optimal performance)
Morale Score: {match_info.home_team_profile.morale_score:.2f}/1.0
Fan Sentiment: {match_info.home_team_profile.fan_sentiment}
Recent Controversy: {'Yes' if match_info.home_team_profile.recent_controversy else 'No'}

Affected Players:
"""
    
    if match_info.home_team_profile.affected_players:
        for player in match_info.home_team_profile.affected_players:
            prompt += f"  - {player.name}: "
            prompt += f"Issues: {', '.join(player.issues)}, "
            prompt += f"Impact Level: {player.impact_level}, "
            prompt += f"Key Player: {'Yes' if player.is_key_player else 'No'}, "
            prompt += f"Performance Modifier: {player.calculate_performance_modifier():.2f}\n"
    else:
        prompt += "  - No significant psychological factors identified\n"
    
    if match_info.home_team_profile.injuries:
        prompt += f"\nInjuries:\n"
        for injury in match_info.home_team_profile.injuries:
            prompt += f"  - {injury['player']}: {injury['type']} ({injury['duration']})\n"
    
    if match_info.home_team_profile.team_news:
        prompt += f"\nRecent Team News:\n"
        for news in match_info.home_team_profile.team_news[:5]:
            prompt += f"  - {news}\n"
    
    prompt += f"""
AWAY TEAM ({match_info.away_team}) PSYCHOLOGICAL PROFILE:
Performance Modifier: {away_modifier:.2f} ({away_modifier*100:.0f}% of optimal performance)
Morale Score: {match_info.away_team_profile.morale_score:.2f}/1.0
Fan Sentiment: {match_info.away_team_profile.fan_sentiment}
Recent Controversy: {'Yes' if match_info.away_team_profile.recent_controversy else 'No'}

Affected Players:
"""
    
    if match_info.away_team_profile.affected_players:
        for player in match_info.away_team_profile.affected_players:
            prompt += f"  - {player.name}: "
            prompt += f"Issues: {', '.join(player.issues)}, "
            prompt += f"Impact Level: {player.impact_level}, "
            prompt += f"Key Player: {'Yes' if player.is_key_player else 'No'}, "
            prompt += f"Performance Modifier: {player.calculate_performance_modifier():.2f}\n"
    else:
        prompt += "  - No significant psychological factors identified\n"
    
    if match_info.away_team_profile.injuries:
        prompt += f"\nInjuries:\n"
        for injury in match_info.away_team_profile.injuries:
            prompt += f"  - {injury['player']}: {injury['type']} ({injury['duration']})\n"
    
    if match_info.away_team_profile.team_news:
        prompt += f"\nRecent Team News:\n"
        for news in match_info.away_team_profile.team_news[:5]:
            prompt += f"  - {news}\n"
    
    # Add scraped odds if available
    if match_info.scraped_odds:
        prompt += "\n=== SCRAPED BOOKMAKER ODDS (For Reference) ===\n"
        for market, odd in match_info.scraped_odds.items():
            prompt += f"  - {market.replace('_', ' ').title()}: {odd}\n"
        prompt += "\nNOTE: These are market odds. Reevaluate them based on psychological factors that may not be fully priced in.\n"
    
    # Add stats if available
    if match_info.stats:
        prompt += "\n=== STATISTICAL DATA ===\n"
        for key, value in match_info.stats.items():
            prompt += f"  - {key.replace('_', ' ').title()}: {value}\n"
    
    prompt += f"""
=== ANALYSIS TASK ===
Using the psychological profiles, performance modifiers, and all available data:

1. Assess how psychological factors will impact this specific match
2. Calculate adjusted win probabilities considering:
   - Team performance modifiers (Home: {home_modifier:.2f}, Away: {away_modifier:.2f})
   - Key player psychological states
   - Team morale and fan sentiment
   - Traditional statistical factors

3. If scraped odds are provided, identify where psychological factors create value opportunities
   (e.g., if a key striker is dealing with divorce, team might underperform despite good form)

4. Recommend AT LEAST 5 specific bets with confidence levels
5. Explain how psychological factors influenced each recommendation

Remember: Your unique edge is incorporating psychological analysis that bookmakers may underweight.
Focus on how individual player welfare affects team performance, especially when key players are impacted.
"""
    
    # Limit content length
    max_length = 6000
    if len(prompt) > max_length:
        prompt = prompt[:max_length] + "\n...[Content truncated for length]"
    
    return prompt


def parse_llm_response(raw: str) -> str:
    """Strip DeepSeek R1 thinking block before running strict validation."""
    clean = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    return clean


async def process_with_openai(system_prompt: str, user_prompt: str, max_retries: int = 3) -> str:
    """Process analysis using Groq/OpenAI-compatible LLM with retries."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    for attempt in range(max_retries):
        try:
            raw = await call_llm(
                messages=messages,
                temperature=0.5,
                max_tokens=5000,
            )
            analysis = parse_llm_response(raw)

            if is_valid_analysis(analysis):
                return analysis

            print(f"Attempt {attempt + 1}: Analysis validation failed, retrying...")
            await asyncio.sleep(2)
        except Exception as e:
            error_msg = str(e)
            print(f"API Error (attempt {attempt + 1}): {error_msg}")

            if "rate limit" in error_msg.lower():
                wait_time = min(2**attempt * 5, 60)
                print(f"Rate limited. Waiting {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            elif attempt == max_retries - 1:
                return f"Error: API request failed after {max_retries} attempts: {error_msg}"

    return "Error: Failed to generate valid analysis after multiple attempts."


def is_valid_analysis(analysis: str) -> bool:
    """Validate the generated analysis"""
    if not analysis or analysis.startswith("Error:"):
        return False
    
    required_sections = [
        "MATCH:",
        "PSYCHOLOGICAL IMPACT SUMMARY:",
        "PERFORMANCE MODIFIERS:",
        "ADJUSTED WIN PROBABILITY:",
        "RECOMMENDED BETS",
        "DETAILED ANALYSIS:"
    ]
    
    for section in required_sections:
        if section not in analysis:
            return False
    
    # Check for win probabilities
    prob_pattern = r'Home (\d+)%\s*\|\s*Draw (\d+)%\s*\|\s*Away (\d+)%'
    prob_match = re.search(prob_pattern, analysis)
    
    if prob_match:
        total = sum(int(prob_match.group(i)) for i in range(1, 4))
        if abs(total - 100) > 2:
            return False
    else:
        return False
    
    # Check for at least 5 betting recommendations
    bet_pattern = r'\d+\.\s+.+@\s+\d+\.\d+'
    bets = re.findall(bet_pattern, analysis)
    if len(bets) < 5:
        return False
    
    return True


def save_analysis(match_info: MatchInfo, analysis: str, output_dir: str = ".") -> Optional[str]:
    """Save comprehensive analysis to file"""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    home_safe = re.sub(r'[\\/*?:"<>|]', "", match_info.home_team)
    away_safe = re.sub(r'[\\/*?:"<>|]', "", match_info.away_team)
    match_id_safe = re.sub(r'[\\/*?:"<>|]', "", match_info.match_id)
    
    filename = f"{match_id_safe}_{home_safe}_vs_{away_safe}_{timestamp}_ENHANCED_analysis.txt"
    filepath = os.path.join(output_dir, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write("="*80 + "\n")
            file.write(f"ENHANCED PSYCHOLOGICAL BETTING ANALYSIS\n")
            file.write("="*80 + "\n\n")
            file.write(f"Match: {match_info.home_team} vs {match_info.away_team}\n")
            file.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            file.write(f"Match Date: {match_info.date}\n")
            file.write(f"Venue: {match_info.venue}\n")
            file.write(f"League: {match_info.league}\n")
            file.write(f"Match ID: {match_info.match_id}\n\n")
            
            file.write("="*80 + "\n")
            file.write("PSYCHOLOGICAL PROFILE SUMMARY\n")
            file.write("="*80 + "\n\n")
            
            # Home team summary
            file.write(f"HOME TEAM: {match_info.home_team}\n")
            file.write(f"Performance Modifier: {match_info.home_team_profile.calculate_team_performance_modifier():.2f}\n")
            file.write(f"Affected Players: {len(match_info.home_team_profile.affected_players)}\n")
            file.write(f"Key Players Affected: {sum(1 for p in match_info.home_team_profile.affected_players if p.is_key_player)}\n")
            file.write(f"Morale: {match_info.home_team_profile.morale_score:.2f}\n")
            file.write(f"Fan Sentiment: {match_info.home_team_profile.fan_sentiment}\n\n")
            
            # Away team summary
            file.write(f"AWAY TEAM: {match_info.away_team}\n")
            file.write(f"Performance Modifier: {match_info.away_team_profile.calculate_team_performance_modifier():.2f}\n")
            file.write(f"Affected Players: {len(match_info.away_team_profile.affected_players)}\n")
            file.write(f"Key Players Affected: {sum(1 for p in match_info.away_team_profile.affected_players if p.is_key_player)}\n")
            file.write(f"Morale: {match_info.away_team_profile.morale_score:.2f}\n")
            file.write(f"Fan Sentiment: {match_info.away_team_profile.fan_sentiment}\n\n")
            
            file.write("="*80 + "\n")
            file.write("AI ANALYSIS\n")
            file.write("="*80 + "\n\n")
            file.write(analysis)
            
            file.write("\n\n" + "="*80 + "\n")
            file.write("DISCLAIMER\n")
            file.write("="*80 + "\n")
            file.write("This analysis incorporates psychological factors and is AI-generated.\n")
            file.write("Odds are illustrative. Always verify with bookmakers and bet responsibly.\n")
            file.write("Past performance and psychological factors do not guarantee future results.\n")
        
        return filepath
    except Exception as e:
        print(f"Error saving analysis to {filepath}: {e}")
        return None


# === Main Processing Function ===
async def process_match_file(md_file_path: str, output_dir: str = ".") -> Optional[str]:
    """Main function to process a match file with enhanced psychological analysis"""
    
    print(f"\n{'='*80}")
    print(f"Processing: {os.path.basename(md_file_path)}")
    print(f"{'='*80}\n")
    
    # Load file
    md_content = load_md_file(md_file_path)
    if not md_content:
        return None
    
    # Extract complete match information
    print("Extracting match information and psychological profiles...")
    match_info = extract_complete_match_info(md_content)
    if not match_info:
        print("Error: Could not extract match information")
        return None
    
    print(f"Match: {match_info.home_team} vs {match_info.away_team}")
    print(f"League: {match_info.league}")
    print(f"Venue: {match_info.venue}\n")
    
    # Display psychological analysis summary
    print("Psychological Analysis Summary:")
    print(f"\nHome Team ({match_info.home_team}):")
    print(f"  - Performance Modifier: {match_info.home_team_profile.calculate_team_performance_modifier():.2f}")
    print(f"  - Affected Players: {len(match_info.home_team_profile.affected_players)}")
    if match_info.home_team_profile.affected_players:
        key_players = [p for p in match_info.home_team_profile.affected_players if p.is_key_player]
        if key_players:
            print(f"  - Key Players Affected: {len(key_players)}")
            for player in key_players:
                print(f"    * {player.name}: {', '.join(player.issues)} (Impact: {player.impact_level})")
    print(f"  - Morale Score: {match_info.home_team_profile.morale_score:.2f}")
    print(f"  - Fan Sentiment: {match_info.home_team_profile.fan_sentiment}")
    
    print(f"\nAway Team ({match_info.away_team}):")
    print(f"  - Performance Modifier: {match_info.away_team_profile.calculate_team_performance_modifier():.2f}")
    print(f"  - Affected Players: {len(match_info.away_team_profile.affected_players)}")
    if match_info.away_team_profile.affected_players:
        key_players = [p for p in match_info.away_team_profile.affected_players if p.is_key_player]
        if key_players:
            print(f"  - Key Players Affected: {len(key_players)}")
            for player in key_players:
                print(f"    * {player.name}: {', '.join(player.issues)} (Impact: {player.impact_level})")
    print(f"  - Morale Score: {match_info.away_team_profile.morale_score:.2f}")
    print(f"  - Fan Sentiment: {match_info.away_team_profile.fan_sentiment}")
    
    if match_info.scraped_odds:
        print(f"\nScraped Odds Found: {len(match_info.scraped_odds)} market(s)")
    
    # Generate analysis
    print("\n" + "="*80)
    print("Generating AI analysis with psychological factors...")
    print("="*80 + "\n")
    
    system_prompt = get_enhanced_system_prompt()
    user_prompt = build_enhanced_match_prompt(match_info)
    
    analysis = await process_with_openai(system_prompt, user_prompt)
    
    if analysis.startswith("Error:"):
        print(f"\n{analysis}")
        return None
    
    # Save analysis
    output_path = save_analysis(match_info, analysis, output_dir)
    
    if output_path:
        print(f"\n{'='*80}")
        print("ANALYSIS COMPLETE")
        print(f"{'='*80}")
        print(f"Full analysis saved to: {output_path}\n")
        
        # Print preview
        print("="*80)
        print("ANALYSIS PREVIEW")
        print("="*80)
        preview_length = 800
        print(analysis[:preview_length])
        if len(analysis) > preview_length:
            print("...\n[See full file for complete analysis]")
        print("\n" + "="*80)
    else:
        print("\nError: Could not save analysis file")
    
    return output_path


# === Entry Point ===
if __name__ == "__main__":
    # Configuration
    md_file_name = "84ac96d7_Serie A_Juventus_vs_Monza_20250427_103224.md"
    
    # Get script directory
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        script_dir = os.getcwd()
        print(f"Warning: Using current working directory: {script_dir}")
    
    md_file_path = os.path.join(script_dir, md_file_name)
    output_directory = script_dir
    
    print("\n" + "="*80)
    print("ENHANCED FOOTBALL PREDICTION SYSTEM")
    print("with Psychological & Contextual Analysis")
    print("="*80)
    print(f"\nInput File: {md_file_name}")
    print(f"Full Path: {md_file_path}")
    print(f"Output Directory: {output_directory}")
    
    from app_config import settings

    # Verify Groq API key
    if not settings.groq_api_key:
        print("\n" + "!"*80)
        print("ERROR: GROQ_API_KEY not configured!")
        print("!"*80)
        print("\nSet environment variables (or .env) like:")
        print("GROQ_API_KEY=your-key")
        print("GROQ_BASE_URL=https://api.groq.com/openai/v1")
        print("GROQ_MODEL=deepseek-r1-distill-llama-70b")
        print("\n" + "!"*80)
    else:
        # Check if file exists
        if not os.path.exists(md_file_path):
            print(f"\n{'!'*80}")
            print(f"ERROR: Input file not found!")
            print(f"{'!'*80}")
            print(f"\nExpected location: {md_file_path}")
            print("Please ensure the MD file is in the same directory as this script.")
        else:
            # Process the file (async LLM call)
            result = asyncio.run(process_match_file(md_file_path, output_directory))
            
            if result:
                print("\n" + "="*80)
                print("SUCCESS!")
                print("="*80)
                print(f"\nYour enhanced analysis is ready at:")
                print(f"{result}")
            else:
                print("\n" + "="*80)
                print("PROCESSING FAILED")
                print("="*80)
                print("\nPlease check the error messages above.")
    
    print("\n" + "="*80)
    print("Script finished.")
    print("="*80 + "\n")