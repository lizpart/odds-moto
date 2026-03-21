// WhatsApp Bot - Football Analysis
require('dotenv').config();

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

const MEMORY_DIR = path.join(__dirname, 'memory');
const PUPPETEER_CACHE_DIR = process.env.PUPPETEER_CACHE_DIR || path.join(__dirname, '.cache', 'puppeteer');
const TELEGRAM_LINK = process.env.TELEGRAM_LINK || 'https://t.me/ProSokaAIbot';
const PAYMENT_HELPER_PATH = path.join(__dirname, '..', 'payments', 'payment_cli.py');
const PAYMENT_CATALOG_PATH = path.join(__dirname, '..', 'payments', 'payment_catalog.json');
const PYTHON_EXECUTABLE = process.env.PYTHON_EXECUTABLE || (process.platform === 'win32' ? 'python' : 'python3');
const PAYMENT_PACKAGES = JSON.parse(fs.readFileSync(PAYMENT_CATALOG_PATH, 'utf8'));
const GENERIC_PAYMENT_ERROR = 'Payment service is temporarily unavailable. Please try again in a moment.';

function resolveBrowserExecutable() {
    const envPath = process.env.PUPPETEER_EXECUTABLE_PATH || process.env.CHROME_PATH || process.env.EDGE_PATH;
    const candidates = [];

    if (envPath) {
        candidates.push(envPath);
    }

    if (process.platform === 'win32') {
        const programFiles = process.env.PROGRAMFILES || 'C:\\Program Files';
        const programFilesX86 = process.env['PROGRAMFILES(X86)'] || 'C:\\Program Files (x86)';
        const localAppData = process.env.LOCALAPPDATA || '';

        candidates.push(
            path.join(programFiles, 'Google', 'Chrome', 'Application', 'chrome.exe'),
            path.join(programFilesX86, 'Google', 'Chrome', 'Application', 'chrome.exe'),
            path.join(localAppData, 'Google', 'Chrome', 'Application', 'chrome.exe'),
            path.join(programFiles, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
            path.join(programFilesX86, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
            path.join(localAppData, 'Microsoft', 'Edge', 'Application', 'msedge.exe')
        );
    } else if (process.platform === 'darwin') {
        candidates.push(
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
        );
    } else {
        candidates.push(
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable',
            '/usr/bin/chromium',
            '/usr/bin/chromium-browser',
            '/usr/bin/microsoft-edge'
        );
    }

    for (const candidate of candidates) {
        if (candidate && fs.existsSync(candidate)) {
            return candidate;
        }
    }

    return null;
}

if (!fs.existsSync(MEMORY_DIR)) {
    fs.mkdirSync(MEMORY_DIR, { recursive: true });
}

if (!fs.existsSync(PUPPETEER_CACHE_DIR)) {
    fs.mkdirSync(PUPPETEER_CACHE_DIR, { recursive: true });
}
process.env.PUPPETEER_CACHE_DIR = PUPPETEER_CACHE_DIR;

function getMidnightEAT() {
    const formatter = new Intl.DateTimeFormat('en-CA', {
        timeZone: 'Africa/Nairobi',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    });
    const parts = formatter.formatToParts(new Date()).reduce((acc, part) => {
        if (part.type !== 'literal') {
            acc[part.type] = part.value;
        }
        return acc;
    }, {});
    return new Date(`${parts.year}-${parts.month}-${parts.day}T23:59:59+03:00`);
}

function isSubscriptionExpired(memory) {
    if (!memory.subscription_expires_at) {
        return true;
    }
    return new Date() > new Date(memory.subscription_expires_at);
}

function getSubscriptionMinutesLeft(memory) {
    if (!memory.subscription_expires_at) {
        return 0;
    }
    const minutesLeft = Math.floor((new Date(memory.subscription_expires_at) - new Date()) / 1000 / 60);
    return Math.max(0, minutesLeft);
}

const STATE = {
    INITIAL: 'initial',
    GREETING_SENT: 'greeting_sent',
    AWAITING_PHONE: 'awaiting_phone',
    PAYMENT_PENDING: 'payment_pending',
    PAYMENT_CONFIRMED: 'payment_confirmed',
    AWAITING_ACTIVATION_PHONE: 'awaiting_activation_phone',
    AWAITING_ACTIVATION_PIN: 'awaiting_activation_pin'
};

function normalizePhoneNumber(value) {
    const digits = String(value || '').replace(/\D/g, '');
    if (digits.length === 9) {
        return `+254${digits}`;
    }
    if (digits.length === 10 && digits.startsWith('0')) {
        return `+254${digits.slice(1)}`;
    }
    if (digits.length === 12 && digits.startsWith('254')) {
        return `+${digits}`;
    }
    return null;
}

function sanitizePaymentErrorMessage(rawMessage) {
    if (!rawMessage || typeof rawMessage !== 'string') {
        return GENERIC_PAYMENT_ERROR;
    }

    const message = rawMessage.trim();
    if (!message) {
        return GENERIC_PAYMENT_ERROR;
    }

    // Never expose Python traceback / module internals to end users.
    const looksLikeDebug = [
        'Traceback (most recent call last)',
        'ModuleNotFoundError',
        'File "',
        'line ',
        'ImportError'
    ].some(pattern => message.includes(pattern));

    if (looksLikeDebug || message.includes('\n')) {
        return GENERIC_PAYMENT_ERROR;
    }

    return message;
}

function readMemory(waId) {
    const file = path.join(MEMORY_DIR, `${waId}.json`);
    if (!fs.existsSync(file)) {
        return null;
    }

    try {
        return JSON.parse(fs.readFileSync(file, 'utf8'));
    } catch (error) {
        console.error('Memory read error', error);
        return null;
    }
}

function writeMemory(waId, obj) {
    const file = path.join(MEMORY_DIR, `${waId}.json`);
    obj.updated_at = new Date().toISOString();
    fs.writeFileSync(file, JSON.stringify(obj, null, 2));
}

function getLocalPredictions(tier) {
    const predictionsDir = path.join(__dirname, '../../cache/predictions');
    const leagues = tier === 1 ? ['EPL'] : ['EPL', 'LaLiga', 'SerieA', 'Bundesliga', 'Ligue1'];
    const predictions = [];

    for (const league of leagues) {
        const leagueDir = path.join(predictionsDir, league);
        if (!fs.existsSync(leagueDir)) {
            continue;
        }

        const files = fs.readdirSync(leagueDir).filter(file => file.endsWith('.json'));
        for (const file of files) {
            try {
                const data = JSON.parse(fs.readFileSync(path.join(leagueDir, file), 'utf8'));
                predictions.push({
                    fixture_id: data.fixture_id,
                    league,
                    match: data.data?.match || 'Unknown',
                    probabilities: data.data?.probabilities || {},
                    summary: data.data?.summary || '',
                    top_bets: data.data?.top_bets || []
                });
            } catch (error) {
                console.error(`Error reading ${file}:`, error.message);
            }
        }
    }

    return predictions;
}

function getDetailedPrediction(matchId) {
    const predictionsDir = path.join(__dirname, '../../cache/predictions');
    const leagues = ['EPL', 'LaLiga', 'SerieA', 'Bundesliga', 'Ligue1'];

    for (const league of leagues) {
        const leagueDir = path.join(predictionsDir, league);
        const filePath = path.join(leagueDir, `${matchId}_enhanced.json`);
        if (!fs.existsSync(filePath)) {
            continue;
        }

        try {
            const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
            return {
                league,
                match: data.data?.match || 'Unknown',
                probabilities: data.data?.probabilities || {},
                summary: data.data?.summary || '',
                top_bets: data.data?.top_bets || []
            };
        } catch (error) {
            console.error('Error reading prediction:', error.message);
        }
    }

    return null;
}

async function initializeMpesaPayment({ userId, packageChoice, phoneNumber }) {
    try {
        return await runPaymentHelper([
            'initiate',
            '--user-id', String(userId),
            '--package', String(packageChoice),
            '--phone-number', String(phoneNumber)
        ]);
    } catch (error) {
        console.error('Shared payment helper initiate error:', error.message);
        return {
            success: false,
            error: sanitizePaymentErrorMessage(error.message)
        };
    }
}

async function verifyMpesaPayment(reference, waId, phoneNumber) {
    try {
        const args = [
            'verify',
            '--reference', String(reference)
        ];

        if (waId) {
            args.push('--platform', 'whatsapp', '--platform-user-id', String(waId));
        }
        if (phoneNumber) {
            args.push('--phone-number', String(phoneNumber));
        }

        return await runPaymentHelper(args);
    } catch (error) {
        console.error('Shared payment helper verify error:', error.message);
        return {
            success: false,
            error: sanitizePaymentErrorMessage(error.message)
        };
    }
}

async function activateExistingSubscription(waId, paymentPhone, pin) {
    try {
        return await runPaymentHelper([
            'activate',
            '--platform', 'whatsapp',
            '--platform-user-id', String(waId),
            '--payment-phone', String(paymentPhone),
            '--pin', String(pin)
        ]);
    } catch (error) {
        console.error('Shared payment helper activate error:', error.message);
        return {
            success: false,
            activated: false,
            error: sanitizePaymentErrorMessage(error.message)
        };
    }
}

async function checkSubscriptionAccess(waId) {
    try {
        return await runPaymentHelper([
            'access',
            '--platform', 'whatsapp',
            '--platform-user-id', String(waId)
        ]);
    } catch (error) {
        console.error('Shared payment helper access error:', error.message);
        return {
            success: false,
            active: false,
            reason: 'access_check_failed',
            error: sanitizePaymentErrorMessage(error.message)
        };
    }
}

function syncMemoryFromAccess(updateMemory, payload) {
    if (!payload || typeof payload !== 'object') {
        return;
    }

    if (payload.expires_at || payload.subscription_expires_at) {
        updateMemory.subscription_expires_at = payload.expires_at || payload.subscription_expires_at;
    }
    if (payload.payment_phone) {
        updateMemory.phone = payload.payment_phone;
    }

    const packageValue = payload.package;
    if (packageValue !== null && packageValue !== undefined) {
        const packageKey = String(packageValue);
        const packageDetails = PAYMENT_PACKAGES[packageKey];
        if (packageDetails) {
            updateMemory.package = packageKey;
            updateMemory.tier = Number(packageKey);
            updateMemory.amount = Number(packageDetails.amount_ksh || updateMemory.amount || 0);
        }
    }
}

function isProtectedCommand(msg) {
    if (msg === 'matches' || msg === 'status' || msg.startsWith('predict ')) {
        return true;
    }
    if (!/^\d+$/.test(msg)) {
        return false;
    }
    // Keep plan choices (1/2) in purchase flow; numeric IDs are longer.
    return msg.length >= 4;
}

function isMenuCommand(msg) {
    return ['hi', 'hello', 'hey', 'start', '/start', 'menu', 'help', '/help'].includes(msg);
}

function isStartOverCommand(msg) {
    const normalized = String(msg || '').trim().toLowerCase().replace(/\s+/g, ' ');
    return normalized === 'start over' || normalized === 'startover' || normalized === '/startover';
}

function buildPlanMenu() {
    return [
        'Welcome to Football Analysis Bot.',
        '',
        'Choose a plan:',
        '1. KSH 10 - Basic Analysis',
        '2. KSH 30 - Premium Analysis + Predictions',
        '3. Activate existing subscription',
        '',
        'Reply with 1, 2, or 3.',
        '',
        'Send "start over" or "startover" anytime to return to this menu.'
    ].join('\n');
}

function runPaymentHelper(args) {
    return new Promise((resolve, reject) => {
        const helper = spawn(PYTHON_EXECUTABLE, [PAYMENT_HELPER_PATH, ...args], {
            cwd: path.join(__dirname, '..', '..'),
            env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
            windowsHide: true,
            shell: false
        });

        let stdout = '';
        let stderr = '';

        helper.stdout.on('data', chunk => {
            stdout += chunk.toString();
        });

        helper.stderr.on('data', chunk => {
            stderr += chunk.toString();
        });

        helper.on('error', error => {
            reject(error);
        });

        helper.on('close', code => {
            const trimmed = stdout.trim();
            if (trimmed) {
                try {
                    const result = JSON.parse(trimmed);
                    if (stderr.trim()) {
                        console.log(stderr.trim());
                    }
                    resolve(result);
                    return;
                } catch (error) {
                    console.error('Payment helper parse error:', trimmed);
                    reject(new Error(GENERIC_PAYMENT_ERROR));
                    return;
                }
            }

            const stderrMessage = stderr.trim();
            if (stderrMessage) {
                console.error('Payment helper stderr:', stderrMessage);
            } else {
                console.error(`Payment helper exited with code ${code} and no stdout payload.`);
            }
            reject(new Error(GENERIC_PAYMENT_ERROR));
        });
    });
}

function formatMatchesResponse(memory) {
    const tier = memory.tier || 1;
    const minutesLeft = getSubscriptionMinutesLeft(memory);
    const tierName = tier === 1 ? 'Basic (EPL)' : 'Premium (All Leagues)';
    const predictions = getLocalPredictions(tier);

    let response = `*${tierName} Plan* - Predictions Available\n\n`;
    if (predictions.length === 0) {
        response += 'No predictions available right now.\n\n';
    } else {
        const byLeague = {};
        for (const prediction of predictions) {
            if (!byLeague[prediction.league]) {
                byLeague[prediction.league] = [];
            }
            byLeague[prediction.league].push(prediction);
        }

        for (const [league, matches] of Object.entries(byLeague)) {
            response += `*${league}* (${matches.length} matches)\n`;
            matches.forEach((match, index) => {
                const probabilities = match.probabilities || {};
                response += `${index + 1}. ${match.match}\n`;
                if (Object.keys(probabilities).length > 0) {
                    response += `   Home ${probabilities.home || 0}% | Draw ${probabilities.draw || 0}% | Away ${probabilities.away || 0}%\n`;
                }
                response += `   ID: ${match.fixture_id}\n\n`;
            });
        }
    }

    response += `Subscription expires in ${minutesLeft} minutes.\n\n`;
    response += 'Reply with a match ID or `predict <match_id>` for detailed analysis.';
    response += `\n\nAlso on Telegram: ${TELEGRAM_LINK}`;
    return response;
}

function formatPredictionResponse(matchId, memory) {
    const prediction = getDetailedPrediction(matchId);
    if (!prediction) {
        return `No prediction found for match ID: ${matchId}\n\nSay "matches" to see available matches.`;
    }

    const probabilities = prediction.probabilities || {};
    const minutesLeft = getSubscriptionMinutesLeft(memory);

    let response = `*${prediction.match}* - ${prediction.league}\n\n`;
    response += '*Probabilities:*\n';
    response += `Home: ${probabilities.home || 0}% | Draw: ${probabilities.draw || 0}% | Away: ${probabilities.away || 0}%\n\n`;

    if (prediction.top_bets && prediction.top_bets.length > 0) {
        response += '*Top Bets:*\n';
        prediction.top_bets.slice(0, 3).forEach((bet, index) => {
            response += `${index + 1}. ${bet.bet || 'Unknown'}\n`;
            response += `   Odds: ${bet.odds || 'N/A'}\n\n`;
        });
    }

    if (prediction.summary) {
        response += `*Analysis:*\n${prediction.summary.substring(0, 500)}...\n\n`;
    }

    response += `${minutesLeft} minutes left on your subscription.\n\n`;
    response += `Also on Telegram: ${TELEGRAM_LINK}`;
    return response;
}

async function processMessage(text, memory, waId) {
    const msg = (text || '').trim().toLowerCase();
    const userState = memory?.state || STATE.INITIAL;
    let response = '';
    let newState = userState;
    let updateMemory = {};

    if (isStartOverCommand(msg)) {
        newState = STATE.GREETING_SENT;
        updateMemory.activation_phone = null;
        response = buildPlanMenu();
        return { response, newState, updateMemory };
    }

    if (msg === 'activate') {
        const access = await checkSubscriptionAccess(waId);
        if (access.success && access.active) {
            syncMemoryFromAccess(updateMemory, access);
            newState = STATE.PAYMENT_CONFIRMED;
            const effectiveMemory = { ...memory, ...updateMemory, state: newState };
            const minutesLeft = getSubscriptionMinutesLeft(effectiveMemory);
            const hours = Math.floor(minutesLeft / 60);
            const minutes = minutesLeft % 60;
            response = [
                'You already have an active subscription.',
                '',
                `Expires in: ${hours}h ${minutes}m`,
                '',
                'Commands: "matches", "predict <id>", "status", or "start over".'
            ].join('\n');
        } else {
            newState = STATE.AWAITING_ACTIVATION_PHONE;
            updateMemory.activation_phone = null;
            response = [
                'Activation started.',
                '',
                'Send the M-Pesa phone number used for payment:',
                '+254712345678'
            ].join('\n');
        }
        return { response, newState, updateMemory };
    }

    const awaitingInputStates = [
        STATE.AWAITING_PHONE,
        STATE.PAYMENT_PENDING,
        STATE.AWAITING_ACTIVATION_PHONE,
        STATE.AWAITING_ACTIVATION_PIN
    ];
    if (isProtectedCommand(msg) && !awaitingInputStates.includes(userState)) {
        const access = await checkSubscriptionAccess(waId);
        if (access.success && access.active) {
            syncMemoryFromAccess(updateMemory, access);
            newState = STATE.PAYMENT_CONFIRMED;
            const effectiveMemory = { ...memory, ...updateMemory, state: newState };

            if (msg === 'matches') {
                response = formatMatchesResponse(effectiveMemory);
            } else if (msg === 'status') {
                const minutesLeft = getSubscriptionMinutesLeft(effectiveMemory);
                const hours = Math.floor(minutesLeft / 60);
                const minutes = minutesLeft % 60;
                response = `Subscription active.\n\nTier: KSH ${effectiveMemory.tier === 1 ? '10' : '30'}\nExpires in: ${hours}h ${minutes}m\n\nSend "matches" or "predict <id>".`;
            } else {
                const matchId = msg.replace(/^predict\s+/i, '').trim();
                if (/^\d+$/.test(matchId)) {
                    response = formatPredictionResponse(matchId, effectiveMemory);
                } else {
                    response = 'Invalid format. Use a numeric match ID, for example: 1379139';
                }
            }
            return { response, newState, updateMemory };
        }

        newState = STATE.GREETING_SENT;
        response = [
            'No active subscription was found.',
            '',
            'Reply with 1 or 2 to pay, or send "activate" to link an existing subscription.'
        ].join('\n');
        return { response, newState, updateMemory };
    }

    switch (userState) {
        case STATE.INITIAL:
            response = buildPlanMenu();
            newState = STATE.GREETING_SENT;
            break;

        case STATE.GREETING_SENT:
            if (isMenuCommand(msg)) {
                response = buildPlanMenu();
            } else if (msg === '3') {
                const access = await checkSubscriptionAccess(waId);
                if (access.success && access.active) {
                    syncMemoryFromAccess(updateMemory, access);
                    newState = STATE.PAYMENT_CONFIRMED;
                    const effectiveMemory = { ...memory, ...updateMemory, state: newState };
                    const minutesLeft = getSubscriptionMinutesLeft(effectiveMemory);
                    const hours = Math.floor(minutesLeft / 60);
                    const minutes = minutesLeft % 60;
                    response = [
                        'You already have an active subscription.',
                        '',
                        `Expires in: ${hours}h ${minutes}m`,
                        '',
                        'Commands: "matches", "predict <id>", "status", or "start over".'
                    ].join('\n');
                } else {
                    newState = STATE.AWAITING_ACTIVATION_PHONE;
                    updateMemory.activation_phone = null;
                    response = [
                        'Activation started.',
                        '',
                        'Send the M-Pesa phone number used for payment:',
                        '+254712345678'
                    ].join('\n');
                }
            } else if (msg === '1' || msg === '2') {
                const packageDetails = PAYMENT_PACKAGES[msg];
                if (!packageDetails) {
                    response = 'Invalid choice. Please reply with 1 or 2.';
                    break;
                }

                const amount = Number(packageDetails.amount_ksh || 0);
                updateMemory = {
                    tier: Number(msg),
                    package: msg,
                    amount
                };
                newState = STATE.AWAITING_PHONE;
                response = [
                    `You selected the ${packageDetails.name} plan for KSH ${amount}.`,
                    '',
                    'Send the M-Pesa number to charge in this format:',
                    '+254712345678'
                ].join('\n');
            } else {
                response = [
                    'Invalid choice.',
                    '',
                    buildPlanMenu()
                ].join('\n');
            }
            break;

        case STATE.AWAITING_PHONE: {
            const packageChoice = memory.package;
            const packageDetails = PAYMENT_PACKAGES[packageChoice];
            const amount = Number(packageDetails?.amount_ksh || memory.amount || 0);
            const phoneNumber = normalizePhoneNumber(text);

            if (!packageChoice || !packageDetails) {
                response = 'Your package selection expired. Reply with 1 or 2 to start again.';
                newState = STATE.GREETING_SENT;
                break;
            }

            if (!phoneNumber) {
                response = [
                    'Please send a valid Safaricom M-Pesa number in this format:',
                    '+254712345678'
                ].join('\n');
                break;
            }

            const paymentResult = await initializeMpesaPayment({
                userId: waId,
                packageChoice,
                phoneNumber
            });

            updateMemory = {
                phone: phoneNumber,
                tier: Number(packageChoice),
                amount,
                package: packageChoice
            };

            if (!paymentResult.success) {
                response = `Payment initiation failed: ${paymentResult.error}\n\nReply with 1 or 2 to try again.`;
                newState = STATE.GREETING_SENT;
                updateMemory.last_payment_error = paymentResult.error;
                updateMemory.payment_reference = null;
                updateMemory.payment_status = null;
            } else {
                const paymentDisplayText = paymentResult.display_text || paymentResult.displayText;
                response = [
                    `Payment request sent for KSH ${amount} to ${phoneNumber}.`,
                    '',
                    paymentDisplayText || 'Check your phone for the M-Pesa prompt.',
                    `Reference: ${paymentResult.reference}`,
                    '',
                    'Approve the M-Pesa prompt, then reply with "verify".',
                    'You can also send "status" to re-check the payment.'
                ].join('\n');
                newState = STATE.PAYMENT_PENDING;
                updateMemory.payment_reference = paymentResult.reference;
                updateMemory.payment_status = paymentResult.status || 'pending';
                updateMemory.last_payment_error = null;
            }
            break;
        }

        case STATE.PAYMENT_PENDING:
            if (msg === 'verify' || msg === 'status') {
                const reference = memory.payment_reference;
                if (!reference) {
                    response = 'No pending payment was found. Reply with 1 or 2 to start again.';
                    newState = STATE.GREETING_SENT;
                    break;
                }

                const verification = await verifyMpesaPayment(reference, waId, memory.phone);
                if (!verification.success) {
                    response = [
                        `I could not verify that payment yet: ${verification.error}`,
                        '',
                        'If you already approved the M-Pesa prompt, wait a few seconds and send "verify" again.'
                    ].join('\n');
                    updateMemory.payment_status = 'pending';
                    break;
                }

                updateMemory.payment_status = verification.status || 'pending';

                if (verification.verified) {
                    const expectedAmount = Number(memory.amount || 0);
                    const paidAmount = Math.round(Number(verification.amount_ksh || verification.amountKsh || 0));

                    if (expectedAmount && paidAmount && expectedAmount !== paidAmount) {
                        response = `Payment amount mismatch. Expected KSH ${expectedAmount} but received KSH ${paidAmount}.\n\nReply with 1 or 2 to start a fresh payment.`;
                        newState = STATE.GREETING_SENT;
                        updateMemory.last_payment_error = `Expected KSH ${expectedAmount}, got KSH ${paidAmount}.`;
                        break;
                    }

                    syncMemoryFromAccess(updateMemory, verification);
                    const activationPin = verification.activation_pin;
                    const activationPhone = verification.payment_phone || verification.phone_number || updateMemory.phone || memory.phone;
                    if (activationPin && activationPhone) {
                        response = [
                            'Payment confirmed.',
                            '',
                            `Your PIN is ${activationPin}.`,
                            `Activation phone: ${activationPhone}.`,
                            'Use this phone + PIN to activate on WhatsApp or Telegram.',
                            '',
                            'Send "matches" to see available predictions.'
                        ].join('\n');
                    } else {
                        response = [
                            'Payment confirmed.',
                            '',
                            'Your subscription is now active.',
                            '',
                            'Send "matches" to see available predictions.'
                        ].join('\n');
                    }
                    newState = STATE.PAYMENT_CONFIRMED;
                    updateMemory.last_payment_error = null;
                } else if (['pending', 'ongoing', 'processing', 'pay_offline'].includes(verification.status)) {
                    response = [
                        `Your payment is still "${verification.status}".`,
                        '',
                        'Complete the M-Pesa prompt on your phone, then send "verify" again.'
                    ].join('\n');
                } else {
                    response = `Payment was not completed. Paystack status: "${verification.status}".\n\nReply with 1 or 2 to start a new payment.`;
                    newState = STATE.GREETING_SENT;
                    updateMemory.last_payment_error = verification.gateway_response || verification.gatewayResponse || verification.status;
                }
            } else {
                response = [
                    'Awaiting payment confirmation.',
                    '',
                    'Approve the M-Pesa prompt on your phone, then send "verify".',
                    'Send "start over" to return to the home menu.'
                ].join('\n');
            }
            break;

        case STATE.AWAITING_ACTIVATION_PHONE: {
            const activationPhone = normalizePhoneNumber(text);
            if (!activationPhone) {
                response = 'Please send a valid payment phone in this format: +254712345678';
                break;
            }
            updateMemory.activation_phone = activationPhone;
            newState = STATE.AWAITING_ACTIVATION_PIN;
            response = 'Now send your 6-digit PIN.';
            break;
        }

        case STATE.AWAITING_ACTIVATION_PIN: {
            const activationPhone = normalizePhoneNumber(memory.activation_phone);
            if (!activationPhone) {
                newState = STATE.AWAITING_ACTIVATION_PHONE;
                response = 'Payment phone not found. Send the payment phone number again.';
                break;
            }

            const pin = String(text || '').replace(/\D/g, '');
            if (pin.length !== 6) {
                response = 'PIN must be 6 digits. Please send your PIN again.';
                break;
            }

            const activation = await activateExistingSubscription(waId, activationPhone, pin);
            if (!activation.success) {
                response = `Activation failed: ${activation.error || 'unexpected error'}`;
                break;
            }

            if (activation.locked) {
                const retrySeconds = Number(activation.retry_after_seconds || 0);
                const retryMinutes = Math.max(1, Math.ceil(retrySeconds / 60));
                response = `Too many failed attempts. Please wait about ${retryMinutes} minute(s) before trying again.`;
                break;
            }

            if (!activation.activated) {
                response = [
                    'Invalid phone or PIN.',
                    '',
                    'Send the correct details, send "activate" to restart activation,',
                    'or send "start over" for the home menu.'
                ].join('\n');
                break;
            }

            syncMemoryFromAccess(updateMemory, activation);
            updateMemory.activation_phone = null;
            updateMemory.last_payment_error = null;
            newState = STATE.PAYMENT_CONFIRMED;
            response = [
                'Activation successful.',
                '',
                `Plan active until: ${activation.expires_at || updateMemory.subscription_expires_at || 'N/A'}`,
                'Send "matches" to see available predictions.'
            ].join('\n');
            break;
        }

        case STATE.PAYMENT_CONFIRMED:
            response = 'Options:\n"matches" - See available matches\n"predict <id>" - Get analysis\n"status" - Check time left\n"activate" - Link existing subscription\n"start over" - Go to home menu';
            break;

        default:
            response = 'Hi! I am the Football Analysis Bot. Type "hi" to start.';
            newState = STATE.INITIAL;
            break;
    }

    return { response, newState, updateMemory };
}

const resolvedBrowserExecutable = resolveBrowserExecutable();
const puppeteerConfig = {
    headless: true,
    args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--no-zygote',
        '--disable-gpu'
    ]
};

if (resolvedBrowserExecutable) {
    puppeteerConfig.executablePath = resolvedBrowserExecutable;
    console.log(`Using browser executable: ${resolvedBrowserExecutable}`);
} else {
    console.log(`Using Puppeteer cache directory: ${PUPPETEER_CACHE_DIR}`);
    console.warn(
        'No local Chrome/Edge executable detected. ' +
        'Using Puppeteer-managed browser binary (installed by `npm install`). ' +
        'If needed, run `npm run install:browser` in frontend/whatsapp.'
    );
}

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: puppeteerConfig,
    webVersionCache: {
        type: 'remote',
        remotePath: 'https://raw.githubusercontent.com/wppconnect-team/wa-version/main/html/2.3000.1015901619-alpha.html'
    }
});

client.on('qr', qr => {
    console.log('\nScan this QR code with your phone:\n');
    qrcode.generate(qr, { small: true });
    console.log('\nOpen WhatsApp on your phone -> Linked Devices -> Link a Device\n');
});

client.on('ready', () => {
    console.log('\n' + '='.repeat(60));
    console.log('WhatsApp Bot is connected and ready.');
    console.log('Listening for incoming messages...');
    console.log('='.repeat(60) + '\n');
});

client.on('message', async msg => {
    try {
        const waId = msg.from;
        const text = msg.body?.trim();
        if (!text || waId.endsWith('@g.us')) {
            return;
        }

        console.log(`Message from ${waId}: ${text}`);

        let memory = readMemory(waId);
        if (!memory) {
            memory = {
                wa_id: waId,
                state: STATE.INITIAL
            };
            writeMemory(waId, memory);
        }

        const { response, newState, updateMemory } = await processMessage(text, memory, waId);

        memory.state = newState;
        if (updateMemory && Object.keys(updateMemory).length > 0) {
            Object.assign(memory, updateMemory);
        }
        writeMemory(waId, memory);

        if (response) {
            await msg.reply(response);
            console.log(`Response sent to ${waId}\n`);
        }
    } catch (error) {
        console.error('Error processing message:', error.message);
    }
});

client.on('disconnected', reason => {
    console.log('Client was disconnected:', reason);
});

console.log('\n' + '='.repeat(60));
console.log('Starting WhatsApp Bot (whatsapp-web.js)');
console.log('='.repeat(60));
console.log('\nMake sure you have your phone nearby with WhatsApp open.\n');

client.initialize();
