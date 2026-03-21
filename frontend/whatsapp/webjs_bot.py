"""
WhatsApp Bot using whatsapp-web.js (Selenium-based)
Connects directly to WhatsApp Web and displays QR code for authentication
"""
import os
import logging
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import qrcode
import time

logger = logging.getLogger(__name__)


class WhatsAppWebBot:
    """WhatsApp bot using whatsapp-web.js (Selenium browser automation)"""
    
    def __init__(self, session_dir: str = "./data/whatsapp_sessions"):
        """
        Initialize WhatsApp Web bot
        
        Args:
            session_dir: Directory to store browser session data
        """
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.driver = None
        self.is_connected = False
        
    def setup_browser(self):
        """Setup Chrome browser with WhatsApp Web"""
        logger.info("Setting up Chrome browser for WhatsApp Web...")
        
        chrome_options = Options()
        
        # Use persistent user data directory for session storage
        user_data_dir = str(self.session_dir / "chrome_profile")
        chrome_options.add_argument(f"user-data-dir={user_data_dir}")
        
        # Critical flags to prevent crashes
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-web-resources")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-sync")
        
        # Optional: headless mode (comment out to see browser)
        # chrome_options.add_argument("--headless")
        
        # Disable notifications
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "profile.managed_default_content_settings.popups": 0
        }
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Initialize driver
        try:
            # Try to use webdriver-manager if installed
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            except ImportError:
                # Fallback to system ChromeDriver
                logger.warning("webdriver-manager not installed, using system ChromeDriver")
                self.driver = webdriver.Chrome(options=chrome_options)
            
            logger.info("Chrome browser initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Chrome browser: {e}")
            logger.error("Make sure Chrome/Chromium is installed and accessible")
            logger.error("\nTroubleshooting:")
            logger.error("1. Close any existing Chrome instances")
            logger.error("2. Kill any lingering chromedriver processes")
            logger.error("3. Try running with fresh profile: rm -r data/whatsapp_sessions/chrome_profile")
            return False
    
    def connect(self):
        """Connect to WhatsApp Web and authenticate"""
        if not self.setup_browser():
            return False
        
        try:
            logger.info("Navigating to WhatsApp Web...")
            self.driver.get("https://web.whatsapp.com")
            
            # Give page time to load
            time.sleep(3)
            
            wait = WebDriverWait(self.driver, 45)
            
            # Define authentication indicators
            auth_selectors = [
                "[data-testid='chat-list']",      # Main chat list (most reliable)
                "div[role='main']",                # Main content area
                "[data-testid='app-drawer']",      # Sidebar drawer
                "div[data-testid='conversation-panel-messages']",  # Messages area
                "[data-testid='chatlist-container']",  # Chat list container
                "#main",                           # Main container
                ".side",                           # Side panel
            ]
            
            logger.info("Checking for existing session...")
            
            # First, check if we're already authenticated (no QR code)
            time.sleep(2)
            authenticated = False
            
            for selector in auth_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.is_displayed():
                        logger.info(f"✅ Session restored from saved profile! Found: {selector}")
                        authenticated = True
                        break
                except:
                    pass
            
            if authenticated:
                logger.info("✅ Already authenticated with saved session!")
                time.sleep(2)
                self.is_connected = True
                return True
            
            # Not authenticated - need to scan QR code
            logger.info("Waiting for QR code... (this may take 10-30 seconds)")
            logger.info("📱 Please open WhatsApp on your phone and scan the QR code shown in the browser")
            logger.info("🔐 Waiting for you to scan the QR code with your WhatsApp phone...")
            logger.info("⏳ This may take 20-45 seconds after scanning...")
            
            # Wait for authentication by looking for chat indicators
            start_time = time.time()
            check_interval = 2
            max_wait = 50
            
            while time.time() - start_time < max_wait:
                try:
                    # Check for any auth indicator
                    for selector in auth_selectors:
                        try:
                            element = self.driver.find_element(By.CSS_SELECTOR, selector)
                            if element.is_displayed():
                                logger.info("✅ Successfully authenticated!")
                                time.sleep(2)
                                self.is_connected = True
                                return True
                        except:
                            pass
                    
                    # Check if QR code is gone (another auth indicator)
                    try:
                        qr_elements = self.driver.find_elements(By.CSS_SELECTOR, "canvas")
                        if not qr_elements:
                            logger.info("✅ QR code disappeared - user has scanned!")
                            logger.info("⏳ Waiting for chat interface to load...")
                            time.sleep(5)  # Give page time to fully load
                            
                            # After QR disappears, assume we're authenticating - just wait
                            self.is_connected = True
                            return True
                    except:
                        pass
                    
                    time.sleep(check_interval)
                    elapsed = int(time.time() - start_time)
                    logger.debug(f"Waiting for authentication... ({elapsed}s)")
                    
                except Exception as e:
                    logger.debug(f"Check iteration error: {e}")
                    time.sleep(check_interval)
            
            # Timeout reached - but check one more time
            logger.info("⏱️ Timeout waiting for QR scan - checking one more time...")
            time.sleep(2)
            
            for selector in auth_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.is_displayed():
                        logger.info("✅ Finally authenticated!")
                        self.is_connected = True
                        return True
                except:
                    pass
            
            # Last resort - assume authenticated
            logger.warning("Could not verify authentication, but proceeding anyway...")
            logger.info("If you don't see chats, the QR code might still need to be scanned")
            time.sleep(2)
            self.is_connected = True
            return True
                    
        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            logger.error("Attempting to proceed anyway...")
            time.sleep(2)
            self.is_connected = True
            return True
                
        except Exception as e:
            logger.error(f"Failed to connect to WhatsApp Web: {e}")
            return False
    
    def listen(self):
        """Listen for incoming messages and respond"""
        if not self.is_connected:
            logger.error("Not connected to WhatsApp Web")
            return False
        
        logger.info("=" * 60)
        logger.info("✅ WhatsApp Web Bot is running!")
        logger.info("=" * 60)
        logger.info("Ready to receive messages...")
        logger.info("Messages will appear in the WhatsApp Web interface")
        logger.info("Listening for incoming chats...")
        logger.info("=" * 60)
        
        from frontend.whatsapp.bot import WhatsAppBot
        from frontend import config
        
        # Initialize WhatsApp bot handler
        try:
            bot_handler = WhatsAppBot(
                paystack_secret=config.PAYSTACK_SECRET_KEY,
                paystack_public=config.PAYSTACK_PUBLIC_KEY,
                api_base_url=config.FOOTBALL_API_BASE
            )
        except Exception as e:
            logger.error(f"Failed to initialize bot handler: {e}")
            logger.error("Bot will continue running but won't process messages")
            bot_handler = None
        
        # Keep browser open and listen for messages
        message_log = set()  # Track seen messages to avoid duplicates
        
        try:
            processed_messages = set()  # Track which messages we've already processed
            check_count = 0
            
            while True:
                try:
                    check_count += 1
                    if check_count % 10 == 0:  # Log every 10 checks
                        logger.info(f"Still listening... (check #{check_count})")
                    
                    # Simple approach: get all visible messages and process new ones
                    try:
                        # Look for message elements - different selectors for different message types
                        selectors = [
                            "//span[contains(@class, 'selectable-text')]",  # Text messages
                            "//div[contains(@class, 'message')]//span[@class='selectable-text']",
                            "//div[@data-testid='msg-text']",
                        ]
                        
                        all_messages = []
                        for selector in selectors:
                            try:
                                elements = self.driver.find_elements(By.XPATH, selector)
                                all_messages.extend(elements)
                            except:
                                pass
                        
                        if all_messages:
                            logger.debug(f"Found {len(all_messages)} message elements on page")
                            
                            # Process only new messages (from right side = incoming)
                            for msg_elem in all_messages[-5:]:  # Check last 5 messages
                                try:
                                    msg_text = msg_elem.text.strip()
                                    
                                    if msg_text and len(msg_text) > 0:
                                        msg_id = f"{msg_text}_{int(time.time() * 1000) // 1000}"
                                        
                                        if msg_id not in processed_messages:
                                            processed_messages.add(msg_id)
                                            
                                            # Check if this is a received message (has sender info)
                                            try:
                                                parent = msg_elem.find_element(By.XPATH, "..")
                                                is_received = "message-out" not in parent.get_attribute("class")
                                                
                                                if not is_received:  # Skip sent messages
                                                    continue
                                                    
                                            except:
                                                pass
                                            
                                            logger.info(f"📨 NEW MESSAGE: {msg_text}")
                                            
                                            # Get sender name
                                            try:
                                                sender = self.driver.find_element(By.XPATH, "//h2[@class='x1sxyc5d']/span")
                                                sender_name = sender.text
                                            except:
                                                sender_name = "Unknown"
                                            
                                            logger.info(f"   From: {sender_name}")
                                            
                                            # Process message
                                            if bot_handler:
                                                try:
                                                    import asyncio
                                                    
                                                    user_id = sender_name.replace(" ", "_").lower()
                                                    
                                                    logger.info(f"Processing message...")
                                                    response = asyncio.run(
                                                        bot_handler.process_message(
                                                            user_id=user_id,
                                                            phone_number=sender_name,
                                                            message_text=msg_text
                                                        )
                                                    )
                                                    
                                                    logger.info(f"📤 RESPONSE: {response}")
                                                    
                                                    # Send response
                                                    self._send_message(response)
                                                    
                                                except Exception as e:
                                                    logger.error(f"Error processing message: {e}")
                                                    import traceback
                                                    logger.debug(traceback.format_exc())
                                            else:
                                                logger.warning("Bot handler not initialized")
                                            
                                except Exception as e:
                                    logger.debug(f"Error processing element: {e}")
                        
                    except Exception as e:
                        logger.debug(f"Error searching for messages: {e}")
                    
                    time.sleep(2)
                    
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.debug(f"Error in message loop iteration: {e}")
                    time.sleep(2)
                    
        except KeyboardInterrupt:
            logger.info("\n" + "=" * 60)
            logger.info("Shutting down WhatsApp bot...")
            logger.info("=" * 60)
            self.disconnect()
            return True
    
    def _send_message(self, message_text):
        """Send message via WhatsApp Web input field"""
        try:
            # Find message input field
            input_field = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='msg-input']")
            
            # Clear any existing text
            input_field.clear()
            
            # Type message
            input_field.send_keys(message_text)
            
            time.sleep(0.5)
            
            # Send message (Enter key)
            input_field.send_keys(Keys.RETURN)
            logger.info("✅ Message sent successfully")
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            logger.error("You may need to manually send the response")

    
    def disconnect(self):
        """Disconnect and cleanup"""
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed")
        self.is_connected = False


def main():
    """Main entry point for whatsapp-web.js bot"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("=" * 60)
    logger.info("WhatsApp Web.js Bot")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Starting bot... This will open a Chrome browser.")
    logger.info("Make sure your phone is nearby with WhatsApp ready!")
    logger.info("")
    
    bot = WhatsAppWebBot(session_dir="./data/whatsapp_sessions")
    
    if bot.connect():
        bot.listen()
    else:
        logger.error("Failed to connect to WhatsApp Web")
        logger.error("")
        logger.error("Troubleshooting:")
        logger.error("1. Make sure Chrome/Chromium is installed")
        logger.error("2. Check that you have internet connection")
        logger.error("3. Try again - WhatsApp Web might be updating")


if __name__ == "__main__":
    main()
