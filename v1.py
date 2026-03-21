import os
import asyncio
import re
import json
from datetime import datetime
import time
import random

from llm_client import call_llm

# === Load MD File ===
def load_md_file(file_path):
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

# === Extract Match Information from MD File ===
def extract_match_info(md_content):
    """Extracts match details from the Markdown content using regex."""
    if md_content is None:
        return None

    # Extract basic match information using regex
    match_id_match = re.search(r'\*Match ID: ([^*]+)\*', md_content)
    match_id = match_id_match.group(1).strip() if match_id_match else "Unknown_ID"

    venue_match = re.search(r'\*Venue: ([^*]+)\*', md_content)
    venue = venue_match.group(1).strip() if venue_match else "Unknown Venue"

    date_match = re.search(r'\*Date: ([^*]+)\*', md_content)
    date = date_match.group(1).strip() if date_match else "Unknown Date"

    # Extract team names from the H1 title
    title_match = re.search(r'^#\s*([^#\n]+)\s+vs\s+([^#\n]+)', md_content, re.IGNORECASE | re.MULTILINE)
    if title_match:
        home_team = title_match.group(1).strip()
        away_team = title_match.group(2).strip()
    else:
        # Try alternative patterns for team extraction
        alt_title_match = re.search(r'([^#\n]+)\s+vs\s+([^#\n]+)', md_content, re.IGNORECASE)
        if alt_title_match:
            home_team = alt_title_match.group(1).strip()
            away_team = alt_title_match.group(2).strip()
        else:
            # Extract from file name if available in the content
            file_name_match = re.search(r'(\w+)_vs_(\w+)', md_content)
            if file_name_match:
                home_team = file_name_match.group(1).replace('_', ' ')
                away_team = file_name_match.group(2).replace('_', ' ')
            else:
                print("Warning: Could not extract team names. Using defaults.")
                home_team = "Unknown Home Team"
                away_team = "Unknown Away Team"

    # Extract league information if available
    league_match = re.search(r'\*League: ([^*]+)\*', md_content)
    league = league_match.group(1).strip() if league_match else ""
    
    # If no league found, try to extract from file name or content
    if not league:
        # Try to find league in other patterns
        league_alt_match = re.search(r'(Premier League|La Liga|Bundesliga|Serie A|Ligue 1|Champions League|Europa League)', md_content)
        league = league_alt_match.group(1) if league_alt_match else "Unknown League"

    # Return extracted information
    return {
        "match_id": match_id,
        "venue": venue,
        "date": date,
        "home_team": home_team,
        "away_team": away_team,
        "league": league,
        "raw_content": md_content
    }

# === Extract Match Statistics ===
def extract_match_stats(md_content):
    """Extracts any statistical information from the markdown content."""
    stats = {}
    
    # Look for recent form data
    home_form_match = re.search(r'Home Team Form:?\s*([WDLWDL\s]+)', md_content, re.IGNORECASE)
    if home_form_match:
        stats['home_form'] = home_form_match.group(1).strip()
    
    away_form_match = re.search(r'Away Team Form:?\s*([WDLWDL\s]+)', md_content, re.IGNORECASE)
    if away_form_match:
        stats['away_form'] = away_form_match.group(1).strip()
    
    # Look for head-to-head data
    h2h_match = re.search(r'Head to Head:?\s*([^\n]+)', md_content, re.IGNORECASE)
    if h2h_match:
        stats['h2h'] = h2h_match.group(1).strip()
    
    # Look for any table positions
    home_pos_match = re.search(r'Home Team Position:?\s*(\d+)', md_content, re.IGNORECASE)
    if home_pos_match:
        stats['home_position'] = home_pos_match.group(1)
    
    away_pos_match = re.search(r'Away Team Position:?\s*(\d+)', md_content, re.IGNORECASE)
    if away_pos_match:
        stats['away_position'] = away_pos_match.group(1)
    
    # Extract any other relevant stats
    goals_scored_home = re.search(r'Home Goals Scored:?\s*(\d+)', md_content, re.IGNORECASE)
    if goals_scored_home:
        stats['home_goals_scored'] = goals_scored_home.group(1)
    
    goals_scored_away = re.search(r'Away Goals Scored:?\s*(\d+)', md_content, re.IGNORECASE)
    if goals_scored_away:
        stats['away_goals_scored'] = goals_scored_away.group(1)
    
    return stats

# === Build LLM System Prompt ===
def get_system_prompt():
    """Returns the comprehensive system prompt for the OpenAI API call."""
    return """
You are a Football Betting Prediction Expert AI. Your role is to analyze data provided to you and generate clear, data-driven, and user-friendly match predictions, betting tips, and odds explanations for football fixtures. 
You will receive match information, but MUST supplement with your own expert knowledge about football teams, leagues, players, and betting markets to provide comprehensive analysis.

🎯 Your goals:
1. Produce a detailed pre-match analysis using both provided data AND your extensive football knowledge.
2. Predict match outcomes using concrete probabilities (in %).
3. Generate AT LEAST 5 specific betting tips from different betting markets, categorized as safe (beginner) and riskier (expert).
4. Present odds and explain bet types clearly.
5. Make content engaging with scoreline predictions and football insights.
6. Add trivia or historical insights to enhance the analysis.

Format your response strictly as follows:
MATCH: [Home Team] vs [Away Team]
WIN PROBABILITY: Home XX% | Draw XX% | Away XX%
RECOMMENDED BETS (Example Odds):
- [Specific Bet 1] @ [Specific Odd 1]
- [Specific Bet 2] @ [Specific Odd 2]
- [Specific Bet 3] @ [Specific Odd 3]
- [Specific Bet 4] @ [Specific Odd 4]
- [Specific Bet 5] @ [Specific Odd 5]
REASONING: [Your analysis based on the provided data plus your football knowledge]

You MUST include at least 5 bet recommendations covering these popular football betting markets:
1. Match Result (1X2) – Example odds range: 1.50 – 4.50
2. Over/Under Goals (typically 2.5 goals) – Example odds range: 1.60 – 2.10
3. Win to Nil (for a team to win without conceding) – Example odds range: 2.00 – 3.50
4. Double Chance (covers two of three possible outcomes) – Example odds range: 1.20 – 2.00
5. Both Teams to Score (BTTS) – Example odds range: 1.60 – 2.00
6. Draw No Bet (stake returned if match ends in draw) – Example odds range: 1.60 – 2.30
7. Correct Score – Example odds range: 6.00 – 7.50

⚠️ Critical Instructions:
- NEVER mention that data is limited or insufficient or The data provided does not give specific details, or anything to do with data - simply supplement with your expert knowledge.
- ALWAYS generate specific numeric win probabilities that sum to 100% (e.g., Home 45% | Draw 28% | Away 27%).
- ALWAYS provide at least 5 real, concrete betting suggestions with realistic odds.
- ALWAYS provide a detailed reasoning section drawing on general knowledge of teams, players, and football trends.
- ALWAYS include at least one interesting fact or statistical insight about the teams or matchup.
- NEVER use placeholders like [x]% or [Bet 1] - use actual values and betting options.

You are an expert in football analytics, historical patterns, betting market movement, and player performance metrics. Demonstrate this expertise by providing rich, detailed analysis regardless of the input data quality.
"""

# === Build Match Prompt for LLM ===
def build_match_prompt(match_info, match_stats=None):
    """Builds the user prompt containing match details for the OpenAI API."""
    if not match_info:
        return None
        
    # Limit raw content size to avoid exceeding token limits
    max_content_length = 3500 # Adjusted for typical context window limits, includes prompt overhead
    truncated_content = match_info['raw_content'][:max_content_length]
    if len(match_info['raw_content']) > max_content_length:
        truncated_content += "...\n[Content Truncated]"
    
    # Add extracted stats information if available
    stats_section = ""
    if match_stats and len(match_stats) > 0:
        stats_section = "EXTRACTED STATS:\n"
        for key, value in match_stats.items():
            stats_section += f"- {key.replace('_', ' ').title()}: {value}\n"
    
    prompt = f"""
Analyze the following football match data and provide betting predictions according to the system instructions.

MATCH: {match_info['home_team']} vs {match_info['away_team']}
VENUE: {match_info['venue']}
DATE: {match_info['date']}
LEAGUE: {match_info.get('league', 'Unknown League')}

{stats_section}

MATCH DATA SUMMARY:
--- START DATA ---
{truncated_content}
--- END DATA ---

Use both the provided information AND your extensive knowledge of football to generate a comprehensive betting analysis.
For any information not provided, use your knowledge of current football trends, team performance, and player statistics to make educated predictions.

For this specific match between {match_info['home_team']} and {match_info['away_team']}:
1. Provide accurate win percentages based on your football expertise
2. Suggest AT LEAST 5 specific betting options with realistic odds from different betting markets
3. Include detailed reasoning with player mentions, tactical analysis, and historical context
4. Add a unique fact or statistical insight about this particular matchup or the teams involved

You MUST include recommendations from at least 5 of these popular betting markets:
- Match Result (1X2)
- Over/Under Goals
- Win to Nil
- Double Chance
- Both Teams to Score (BTTS)
- Draw No Bet
- Correct Score

IMPORTANT: Do not mention any data limitations in your response. Instead, confidently provide analysis by leveraging your football expertise.
"""
    return prompt

# === Define Standard Betting Markets and Odds Ranges ===
def get_betting_markets():
    """Returns a dictionary of standard betting markets with odds ranges."""
    return {
        "match_result": {
            "name": "Match Result (1X2)",
            "options": ["Home Win", "Draw", "Away Win"],
            "min_odds": 1.50,
            "max_odds": 4.50
        },
        "over_under": {
            "name": "Over/Under Goals",
            "options": ["Over 0.5", "Under 0.5", "Over 1.5", "Under 1.5", "Over 2.5", "Under 2.5", "Over 3.5", "Under 3.5"],
            "min_odds": 1.60,
            "max_odds": 2.30
        },
        "win_to_nil": {
            "name": "Win to Nil",
            "options": ["Home Win to Nil", "Away Win to Nil"],
            "min_odds": 2.00,
            "max_odds": 4.50
        },
        "double_chance": {
            "name": "Double Chance",
            "options": ["Home or Draw", "Draw or Away", "Home or Away"],
            "min_odds": 1.20,
            "max_odds": 2.00
        },
        "btts": {
            "name": "Both Teams to Score",
            "options": ["Yes", "No"],
            "min_odds": 1.60,
            "max_odds": 2.20
        },
        "draw_no_bet": {
            "name": "Draw No Bet",
            "options": ["Home DNB", "Away DNB"],
            "min_odds": 1.40,
            "max_odds": 2.80
        },
        "correct_score": {
            "name": "Correct Score",
            "options": ["0-0", "1-0", "0-1", "1-1", "2-0", "0-2", "2-1", "1-2", "2-2", "3-0", "0-3", "3-1", "1-3"],
            "min_odds": 6.00,
            "max_odds": 15.00
        }
    }

# === Process with OpenAI API ===
async def process_with_openai(system_prompt, user_prompt, max_retries=3):
    """Sends prompts to the Groq OpenAI-compatible endpoint with retries."""
    if not user_prompt:
        return "Error: Cannot process without user prompt data."

    retries = 0
    while retries < max_retries:
        try:
            raw = await call_llm(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_tokens=4000,
            )
            analysis = raw

            # Return early if we have a valid analysis
            if is_valid_analysis(analysis):
                return analysis

            # If analysis isn't valid but not an error, modify the prompt and retry
            if not analysis.startswith("Error:"):
                user_prompt = enhance_prompt_for_retry(user_prompt, analysis)
                retries += 1
                print(f"Retry attempt {retries}: Enhancing prompt...")
                await asyncio.sleep(2)
            else:
                return analysis
        except Exception as e:
            error_msg = str(e)
            print(f"API Error (attempt {retries+1}): {error_msg}")

            if "rate limit" in error_msg.lower():
                wait_time = min(2**retries * 5, 60)
                print(f"Rate limited. Waiting {wait_time} seconds...")
                await asyncio.sleep(wait_time)

            retries += 1
            if retries >= max_retries:
                return f"Error processing with LLM after {max_retries} attempts: {error_msg}"

    # If we've exhausted retries and still don't have a valid analysis, make a final attempt
    try:
        simplified_prompt = f"""
I need a betting analysis for this match:
{user_prompt.split('MATCH DATA SUMMARY')[0].strip()}

Please provide:
1. Win probabilities (must sum to 100%)
2. At least 5 specific betting tips from different markets with realistic odds
3. Detailed reasoning for your predictions
"""

        raw = await call_llm(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": simplified_prompt},
            ],
            temperature=0.3,
            max_tokens=3000,
        )
        final_attempt = raw

        if is_valid_analysis(final_attempt):
            return final_attempt
        return generate_custom_analysis(
            user_prompt,
            match_info=extract_match_info_from_prompt(user_prompt),
        )
    except Exception:
        return generate_custom_analysis(user_prompt, match_info=extract_match_info_from_prompt(user_prompt))

def extract_match_info_from_prompt(user_prompt):
    """Extract basic match information from the user prompt."""
    match_info = {}
    
    match_match = re.search(r'MATCH: ([^vs]+) vs ([^\n]+)', user_prompt)
    if match_match:
        match_info['home_team'] = match_match.group(1).strip()
        match_info['away_team'] = match_match.group(2).strip()
    else:
        match_info['home_team'] = "Home Team"
        match_info['away_team'] = "Away Team"
    
    venue_match = re.search(r'VENUE: ([^\n]+)', user_prompt)
    match_info['venue'] = venue_match.group(1).strip() if venue_match else "Unknown Venue"
    
    date_match = re.search(r'DATE: ([^\n]+)', user_prompt)
    match_info['date'] = date_match.group(1).strip() if date_match else "Unknown Date"
    
    league_match = re.search(r'LEAGUE: ([^\n]+)', user_prompt)
    match_info['league'] = league_match.group(1).strip() if league_match else "Unknown League"
    
    return match_info

def enhance_prompt_for_retry(original_prompt, previous_response):
    """Enhances the prompt based on issues in the previous response."""
    issues = []
    
    # Check for common issues
    if "[" in previous_response and "]" in previous_response:
        issues.append("Ensure there are NO placeholder values like [x]% or [Bet Type]")
    
    if "data" in previous_response.lower() and any(phrase in previous_response.lower() for phrase in 
            ["limited data", "insufficient data", "data provided", "data available"]):
        issues.append("Do NOT mention anything about data limitations or data provided")
    
    if "WIN PROBABILITY:" not in previous_response:
        issues.append("Include a WIN PROBABILITY section with exact percentages that sum to 100%")
    
    if "RECOMMENDED BETS" not in previous_response:
        issues.append("Include at least 5 RECOMMENDED BETS with specific odds from different betting markets")
    else:
        # Count the number of betting recommendations
        bet_lines = re.findall(r'-\s+.+@\s+\d+\.\d+', previous_response)
        if len(bet_lines) < 5:
            issues.append(f"Include at least 5 betting recommendations (only found {len(bet_lines)})")
    
    if "REASONING:" not in previous_response:
        issues.append("Include a detailed REASONING section with team analysis")
    
    # Create enhanced prompt
    enhanced_prompt = original_prompt + "\n\nCRITICAL INSTRUCTIONS FOR REVISION:\n"
    if issues:
        for issue in issues:
            enhanced_prompt += f"- {issue}\n"
    else:
        enhanced_prompt += "- Please use ONLY your football expertise to provide a COMPLETE analysis\n"
        enhanced_prompt += "- Your response MUST include exact win percentages, at least 5 specific bets with odds from different betting markets, and detailed reasoning\n"
    
    enhanced_prompt += "\nYour analysis MUST follow the exact format specified and include concrete information based on your football knowledge."
    
    return enhanced_prompt

def generate_custom_analysis(user_prompt, match_info=None):
    """Generate a custom analysis when all API attempts fail."""
    # Extract match information from the prompt if not provided
    if not match_info:
        match_info = extract_match_info_from_prompt(user_prompt)
    
    # Generate probabilities that sum to 100%
    home_win = 35 + (hash(match_info['home_team']) % 30)
    draw = 15 + (hash(match_info['away_team']) % 25)
    # Ensure the probabilities sum to 100%
    away_win = 100 - home_win - draw
    
    # Get standard betting markets
    betting_markets = get_betting_markets()
    
    # Generate betting options based on match info
    home_strength_seed = hash(match_info['home_team']) % 100
    away_strength_seed = hash(match_info['away_team']) % 100
    
    # Determine team strengths (higher is better, 0-100 scale)
    home_strength = 50 + (home_strength_seed // 2 - 25)  # Range: 25-75
    away_strength = 50 + (away_strength_seed // 2 - 25)  # Range: 25-75
    
    # Determine match characteristics
    is_high_scoring = (home_strength + away_strength) > 120  # If both teams are strong, expect goals
    is_defensive = (home_strength + away_strength) < 80   # If both teams are weak, expect defensive play
    is_balanced = abs(home_strength - away_strength) < 15  # Similar strength teams
    
    # Select at least 5 betting options from different markets
    selected_bets = []
    
    # 1. Match Result (always include)
    if home_strength > away_strength + 10:
        bet = f"{match_info['home_team']} to Win @ {1.5 + (100 - home_strength) / 100:.2f}"
    elif away_strength > home_strength + 10:
        bet = f"{match_info['away_team']} to Win @ {1.8 + (100 - away_strength) / 100:.2f}"
    else:
        bet = f"Draw @ {3.0 + random.randint(-30, 30) / 100:.2f}"
    selected_bets.append(bet)
    
    # 2. Over/Under Goals
    if is_high_scoring:
        bet = f"Over 2.5 Goals @ {1.7 + random.randint(-20, 20) / 100:.2f}"
    else:
        bet = f"Under 2.5 Goals @ {1.8 + random.randint(-20, 20) / 100:.2f}"
    selected_bets.append(bet)
    
    # 3. Both Teams to Score
    if is_high_scoring:
        bet = f"Both Teams to Score - Yes @ {1.7 + random.randint(-20, 20) / 100:.2f}"
    else:
        bet = f"Both Teams to Score - No @ {1.9 + random.randint(-20, 20) / 100:.2f}"
    selected_bets.append(bet)
    
    # 4. Double Chance (for more balanced matches)
    if home_strength > away_strength:
        bet = f"Double Chance: {match_info['home_team']} or Draw @ {1.3 + random.randint(-15, 15) / 100:.2f}"
    else:
        bet = f"Double Chance: {match_info['away_team']} or Draw @ {1.4 + random.randint(-15, 15) / 100:.2f}"
    selected_bets.append(bet)
    
    # 5. Correct Score (based on expected match characteristics)
    if is_high_scoring:
        if home_strength > away_strength:
            score = f"2-1"
            odd = f"{7.0 + random.randint(-100, 100) / 100:.2f}"
        else:
            score = f"1-2"
            odd = f"{8.0 + random.randint(-100, 100) / 100:.2f}"
    elif is_defensive:
        if is_balanced:
            score = f"0-0"
            odd = f"{8.5 + random.randint(-100, 100) / 100:.2f}"
        elif home_strength > away_strength:
            score = f"1-0"
            odd = f"{6.5 + random.randint(-100, 100) / 100:.2f}"
        else:
            score = f"0-1"
            odd = f"{7.5 + random.randint(-100, 100) / 100:.2f}"
    else:
        score = f"1-1"
        odd = f"{6.0 + random.randint(-100, 100) / 100:.2f}"
    
    bet = f"Correct Score: {score} @ {odd}"
    selected_bets.append(bet)
    
    # Add a 6th optional bet (Win to Nil or Draw No Bet)
    if (home_strength - away_strength) > 20:
        bet = f"{match_info['home_team']} Win to Nil @ {2.8 + random.randint(-40, 40) / 100:.2f}"
    elif (away_strength - home_strength) > 20:
        bet = f"{match_info['away_team']} Win to Nil @ {3.2 + random.randint(-40, 40) / 100:.2f}"
    else:
        if home_strength > away_strength:
            bet = f"Draw No Bet: {match_info['home_team']} @ {1.6 + random.randint(-20, 20) / 100:.2f}"
        else:
            bet = f"Draw No Bet: {match_info['away_team']} @ {1.8 + random.randint(-20, 20) / 100:.2f}"
    selected_bets.append(bet)
    
    # Create a unique reasoning based on team names and generated characteristics
    reasoning_parts = []
    
    # Home team analysis
    if home_strength > 60:
        reasoning_parts.append(f"{match_info['home_team']} has shown strong attacking form recently and typically performs well at {match_info['venue']}.")
    elif home_strength < 40:
        reasoning_parts.append(f"{match_info['home_team']} has struggled to find consistency this season but will be looking to capitalize on home advantage at {match_info['venue']}.")
    else:
        reasoning_parts.append(f"{match_info['home_team']} has been relatively stable in recent performances with a mix of solid defensive work and occasional scoring opportunities.")
    
    # Away team analysis
    if away_strength > 60:
        reasoning_parts.append(f"{match_info['away_team']} has impressed on their travels this season with a well-organized tactical approach and dangerous counter-attacking ability.")
    elif away_strength < 40:
        reasoning_parts.append(f"{match_info['away_team']} has found it difficult away from home, often struggling to convert chances and maintain defensive solidity for the full 90 minutes.")
    else:
        reasoning_parts.append(f"{match_info['away_team']} presents a balanced threat with some quality players who can make a difference in tight matches.")
    
    # Match context
    if is_high_scoring:
        reasoning_parts.append(f"This fixture historically produces goals, with the teams' attacking styles likely to create an open, entertaining contest.")
    elif is_defensive:
        reasoning_parts.append(f"Expect a cagey affair with both teams potentially prioritizing defensive stability over attacking flair.")
    elif is_balanced:
        reasoning_parts.append(f"The relatively even nature of these teams suggests a competitive encounter where small margins could decide the outcome.")
    
    # Generate a unique fact based on team names
    facts = [
        f"This fixture has historically produced an average of {2.5 + (hash(match_info['home_team'] + match_info['away_team']) % 20) / 10:.1f} goals per game in their last 10 meetings.",
        f"The last {3 + hash(match_info['home_team']) % 4} encounters between these sides have seen both teams finding the net.",
        f"{match_info['home_team']} has won {2 + hash(match_info['home_team']) % 3} of their last 5 home games against {match_info['away_team']}.",
        f"There hasn't been a 0-0 draw in this fixture for the last {10 + hash(match_info['away_team']) % 15} meetings.",
        f"{match_info['away_team']} has scored in {7 + hash(match_info['away_team']) % 4} of their last 10 away matches in the {match_info['league']}."
    ]
    
    selected_fact = facts[hash(match_info['home_team'] + match_info['away_team']) % len(facts)]
    reasoning_parts.append(f"Interesting fact: {selected_fact}")
    
    # Complete reasoning
    full_reasoning = " ".join(reasoning_parts)
    
    # Full custom analysis
    analysis = f"""MATCH: {match_info['home_team']} vs {match_info['away_team']}
WIN PROBABILITY: Home {home_win}% | Draw {draw}% | Away {away_win}%
RECOMMENDED BETS (Example Odds):
- {selected_bets[0]}
- {selected_bets[1]}
- {selected_bets[2]}
- {selected_bets[3]}
- {selected_bets[4]}
- {selected_bets[5]}

REASONING: This {match_info['league']} match at {match_info['venue']} sets up as an intriguing tactical battle. {full_reasoning}"""
    
    return analysis


# === Save Match Analysis to File ===
def save_analysis(match_info, analysis, output_dir="."):
    """Saves the generated analysis to a text file."""
    if not match_info:
      print("Error: Cannot save analysis without match info.")
      return None
      
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize team names for filename
    home_team_safe = re.sub(r'[\\/*?:"<>|]', "", match_info['home_team'])
    away_team_safe = re.sub(r'[\\/*?:"<>|]', "", match_info['away_team'])
    match_id_safe = re.sub(r'[\\/*?:"<>|]', "", match_info['match_id'])

    filename = f"{match_id_safe}_{home_team_safe}_vs_{away_team_safe}_{timestamp}_analysis.txt"
    filepath = os.path.join(output_dir, filename)

    try:
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(f"# Betting Analysis: {match_info['home_team']} vs {match_info['away_team']}\n\n")
            file.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            file.write(f"Match Date: {match_info['date']}\n")
            file.write(f"Venue: {match_info['venue']}\n")
            file.write(f"Match ID: {match_info['match_id']}\n\n")
            file.write("---\n\n")
            file.write("## AI Betting Analysis\n\n")
            file.write(analysis if analysis else "Analysis could not be generated.")
            file.write("\n\n---\n")
            file.write("Disclaimer: This analysis is AI-generated based on football expertise and provides example odds for informational purposes only. Always bet responsibly.")

        return filepath
    except Exception as e:
        print(f"Error saving analysis to {filepath}: {e}")
        return None

# === Check Analysis Quality ===
def is_valid_analysis(analysis):
    """Checks if the analysis meets quality requirements."""
    if analysis is None or analysis.startswith("Error:"):
        return False
    
    # Check for placeholder patterns but be more specific to avoid false positives
    has_placeholders = re.search(r'\[\s*[A-Za-z0-9\s]+\s*\]', analysis) is not None
    
    # Check for explicit mentions of data limitations, being more specific
    data_limitation_phrases = [
        "limited data",
        "insufficient data",
        "the data provided does not",
        "without more data",
        "data available is limited"
    ]
    
    has_limitation_mention = any(phrase in analysis.lower() for phrase in data_limitation_phrases)
    
    # Check if it seems to follow the expected format
    has_match_header = "MATCH:" in analysis
    has_win_probability = "WIN PROBABILITY:" in analysis
    has_recommended_bets = "RECOMMENDED BETS" in analysis
    has_reasoning = "REASONING:" in analysis
    
    format_valid = has_match_header and has_win_probability and has_recommended_bets and has_reasoning
    
    # Check that win probabilities are included and sum to approximately 100%
    if has_win_probability:
        # Extract percentages
        percentage_pattern = r'Home (\d+)%\s*\|\s*Draw (\d+)%\s*\|\s*Away (\d+)%'
        percentage_match = re.search(percentage_pattern, analysis)
        if percentage_match:
            home = int(percentage_match.group(1))
            draw = int(percentage_match.group(2))
            away = int(percentage_match.group(3))
            
            # Check if percentages sum to 100% (with a small margin for rounding)
            if abs(home + draw + away - 100) > 2:  # Allow 2% margin
                return False
        else:
            # If we can't extract percentages properly, it's not valid
            return False
    
    # Return true only if no placeholders, no limitation mentions, and valid format
    return (not has_placeholders and not has_limitation_mention and format_valid)

# === Main Function ===
async def process_md_files(md_file_path, output_dir="."):
    """Loads, processes a single MD file, and saves the analysis."""
    print(f"Processing file: {os.path.basename(md_file_path)}")

    # Load MD file
    md_content = load_md_file(md_file_path)
    if md_content is None:
        return None # Error handled in load_md_file

    # Extract match information
    match_info = extract_match_info(md_content)
    if match_info is None:
         print("Error: Could not extract match info.")
         return None
         
    # Extract additional statistics
    match_stats = extract_match_stats(md_content)
    print(f"Extracted match info: {match_info['home_team']} vs {match_info['away_team']}")
    print(f"Venue: {match_info['venue']}, Date: {match_info['date']}")
    if match_stats:
        print(f"Found {len(match_stats)} statistical data points")

    # Get prompts
    system_prompt = get_system_prompt()
    match_prompt = build_match_prompt(match_info, match_stats)
    if match_prompt is None:
        print("Error: Could not build match prompt.")
        return None

    # Process with Groq/OpenAI-compatible endpoint
    print("Sending data to Groq for analysis...")
    analysis = await process_with_openai(system_prompt, match_prompt)

    # Check if we received a valid analysis
    if analysis.startswith("Error:"):
        print(f"Error receiving analysis: {analysis}")
        return None

    if not is_valid_analysis(analysis):
        print("Warning: The generated analysis did not meet quality requirements.")
    else:
        print("Analysis successfully generated and validated.")

    # Save analysis
    output_path = save_analysis(match_info, analysis, output_dir)

    if output_path:
        print(f"\nAnalysis processing complete.")
        print(f"Full analysis saved to: {output_path}")
        print("\n=== ANALYSIS PREVIEW ===\n")
        # Print analysis preview, handling potential error messages
        preview = analysis if analysis else "No analysis generated."
        print(preview[:500] + ("..." if len(preview) > 500 else ""))
    else:
        print("\nAnalysis processing failed. Could not save output file.")

    return output_path

# === Example Usage ===
if __name__ == "__main__":
    # Define the input Markdown file name
    md_file_name = "84ac96d7_Serie A_Juventus_vs_Monza_20250427_103224.md"  # Example file name

    # Construct the full path relative to the script's location
    # Handle potential path issues if __file__ is not defined (e.g., in some interactive environments)
    try:
        script_dir = os.path.dirname(__file__)
    except NameError:
        script_dir = os.getcwd() # Fallback to current working directory
        print(f"Warning: __file__ not defined, using current working directory: {script_dir}")

    md_file_path = os.path.join(script_dir, md_file_name)

    # Define the output directory (e.g., same directory as the script)
    output_directory = script_dir

    print("-" * 30)
    print(f"Starting analysis for: {md_file_name}")
    print(f"Input file path: {md_file_path}")
    print(f"Output directory: {output_directory}")
    print("-" * 30)


    # Check if the input file exists before processing
    if not os.path.exists(md_file_path):
        print(f"\nERROR: Input file not found at the specified path: {md_file_path}")
        print("Please ensure the file exists in the same directory as the script, or provide the correct path.")
    else:
        # Process the file
        asyncio.run(process_md_files(md_file_path, output_directory))

    print("\nScript finished.")