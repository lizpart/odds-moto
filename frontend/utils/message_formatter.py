"""
Message Formatter - Formats API responses for WhatsApp and Telegram
"""
import json
from typing import Dict, List, Optional
from frontend.utils.constants import TELEGRAM_LINK, MAX_MESSAGE_LENGTH, TELEGRAM_MESSAGE_LIMIT


class MessageFormatter:
    """Formats predictions and analysis for messaging platforms"""

    @staticmethod
    def format_fixtures(fixtures_data: Dict) -> str:
        """Format fixtures for display"""
        if not fixtures_data.get('success'):
            return "Unable to fetch fixtures. Please try again."

        fixtures = fixtures_data.get('fixtures', [])
        if not fixtures:
            return "No fixtures available for today."

        message = "⚽ *Today's Fixtures*\n\n"
        
        for i, fixture in enumerate(fixtures[:10], 1):  # Limit to 10
            match = fixture.get('match', 'Unknown match')
            time = fixture.get('time', 'TBA')
            league = fixture.get('league', '')
            status = fixture.get('status', 'NS')
            
            message += f"{i}. *{match}*\n"
            message += f"   ⏰ {time}\n"
            message += f"   🏆 {league}\n"
            message += f"   Status: {status}\n\n"

        message += f"📱 More on Telegram: {TELEGRAM_LINK}"
        return message

    @staticmethod
    def format_prediction(analysis_data: Dict) -> str:
        """Format prediction and analysis for display"""
        if not analysis_data.get('success'):
            return "Unable to fetch prediction. Please try again."

        match = analysis_data.get('match', 'Unknown match')
        probabilities = analysis_data.get('probabilities', {})
        top_bets = analysis_data.get('top_bets', [])
        summary = analysis_data.get('summary', '')
        reasoning = analysis_data.get('reasoning', '')

        message = f"📊 *{match}*\n\n"
        
        # Win Probabilities
        message += "*Win Probability:*\n"
        message += f"🏠 Home: {probabilities.get('home', 0)}%\n"
        message += f"🤝 Draw: {probabilities.get('draw', 0)}%\n"
        message += f"✈️ Away: {probabilities.get('away', 0)}%\n\n"

        # Top Bets
        if top_bets:
            message += "*Top Betting Recommendations:*\n"
            for bet in top_bets[:3]:
                bet_name = bet.get('bet', 'Unknown')
                odds = bet.get('odds', 'N/A')
                message += f"• {bet_name} @ {odds}\n"
            message += "\n"

        # Summary
        if summary:
            message += f"*Analysis:* {summary}\n\n"

        if reasoning:
            message += f"*Detailed Reasoning:*\n{reasoning}\n\n"

        message += f"📱 More on Telegram: {TELEGRAM_LINK}"
        return message

    @staticmethod
    def format_stats(stats_data: Dict) -> str:
        """Format team statistics for display"""
        if not stats_data.get('success'):
            return "Unable to fetch statistics. Please try again."

        match = stats_data.get('match', 'Unknown match')
        home_team = stats_data.get('home_team', {})
        away_team = stats_data.get('away_team', {})

        message = f"📈 *Statistics: {match}*\n\n"

        # Home Team Stats
        message += f"*{home_team.get('name', 'Home Team')}*\n"
        message += f"Form: {home_team.get('form', 'N/A')}\n"
        message += f"Goals Scored: {home_team.get('goals_for', 0)}\n"
        message += f"Goals Against: {home_team.get('goals_against', 0)}\n"
        message += f"Win Rate: {home_team.get('win_rate', 0)}%\n\n"

        # Away Team Stats
        message += f"*{away_team.get('name', 'Away Team')}*\n"
        message += f"Form: {away_team.get('form', 'N/A')}\n"
        message += f"Goals Scored: {away_team.get('goals_for', 0)}\n"
        message += f"Goals Against: {away_team.get('goals_against', 0)}\n"
        message += f"Win Rate: {away_team.get('win_rate', 0)}%\n\n"

        message += f"📱 More on Telegram: {TELEGRAM_LINK}"
        return message

    @staticmethod
    def split_long_message(message: str, platform: str = "whatsapp") -> List[str]:
        """Split long messages to respect platform limits"""
        limit = MAX_MESSAGE_LENGTH if platform == "whatsapp" else TELEGRAM_MESSAGE_LIMIT
        
        if len(message) <= limit:
            return [message]

        messages = []
        current_message = ""
        
        for line in message.split('\n'):
            if len(current_message) + len(line) + 1 > limit:
                messages.append(current_message)
                current_message = line + "\n"
            else:
                current_message += line + "\n"
        
        if current_message:
            messages.append(current_message)

        return messages

    @staticmethod
    def add_telegram_footer(message: str) -> str:
        """Add Telegram link footer to message"""
        if "Telegram" not in message:
            message += f"\n\n📱 {TELEGRAM_LINK}"
        return message


class LeagueFormatter:
    """Format league/tournament specific predictions"""

    LEAGUE_NAMES = {
        "39": "Premier League",
        "135": "Serie A",
        "140": "La Liga",
        "78": "Bundesliga",
        "61": "Ligue 1",
        "94": "Championship",
        "401": "MLS",
        "71": "Scottish Premiership",
    }

    @staticmethod
    def format_league_fixtures(fixtures_data: Dict, league_id: str) -> str:
        """Format fixtures for a specific league"""
        league_name = LeagueFormatter.LEAGUE_NAMES.get(league_id, f"League {league_id}")
        
        fixtures = fixtures_data.get('fixtures', [])
        filtered = [f for f in fixtures if str(f.get('league_id')) == league_id]

        if not filtered:
            return f"No fixtures available for {league_name} today."

        message = f"⚽ *{league_name} - Today's Fixtures*\n\n"
        
        for i, fixture in enumerate(filtered[:10], 1):
            match = fixture.get('match', 'Unknown')
            time = fixture.get('time', 'TBA')
            message += f"{i}. {match} @ {time}\n"

        message += f"\n📱 {TELEGRAM_LINK}"
        return message
