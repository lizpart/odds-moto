#!/usr/bin/env node

/**
 * Multi-Bot Launcher
 * Starts both WhatsApp and Telegram bots in parallel.
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

const activeProcesses = [];
const whatsappCacheDir = process.env.PUPPETEER_CACHE_DIR || path.join(__dirname, 'whatsapp', '.cache', 'puppeteer');

fs.mkdirSync(whatsappCacheDir, { recursive: true });
process.env.PUPPETEER_CACHE_DIR = whatsappCacheDir;

function resolvePythonExecutable() {
    if (process.env.PYTHON_EXECUTABLE) {
        return process.env.PYTHON_EXECUTABLE;
    }

    const projectRoot = path.join(__dirname, '..');
    const candidates = process.platform === 'win32'
        ? [
            path.join(projectRoot, '.venv', 'Scripts', 'python.exe'),
            path.join(projectRoot, 'venv', 'Scripts', 'python.exe'),
            'python'
        ]
        : [
            path.join(projectRoot, '.venv', 'bin', 'python'),
            path.join(projectRoot, 'venv', 'bin', 'python'),
            'python3',
            'python'
        ];

    for (const candidate of candidates) {
        if (!candidate) {
            continue;
        }
        if (candidate === 'python' || candidate === 'python3' || fs.existsSync(candidate)) {
            return candidate;
        }
    }

    return process.platform === 'win32' ? 'python' : 'python3';
}

function resolveNpmExecutable() {
    return process.platform === 'win32' ? 'npm.cmd' : 'npm';
}

function runSetupCommand(command, args, cwd, label) {
    return new Promise((resolve, reject) => {
        console.log(`[setup] ${label}`);
        let spawnCommand = command;
        let spawnArgs = args;

        if (process.platform === 'win32' && String(command).toLowerCase().endsWith('.cmd')) {
            const commandLine = [command, ...args].join(' ');
            spawnCommand = process.env.ComSpec || 'cmd.exe';
            spawnArgs = ['/d', '/s', '/c', commandLine];
        }

        const proc = spawn(spawnCommand, spawnArgs, {
            cwd,
            stdio: 'inherit',
            shell: false,
            env: { ...process.env },
        });

        proc.on('error', (err) => reject(err));
        proc.on('close', (code) => {
            if (code === 0) {
                resolve();
            } else {
                reject(new Error(`${label} failed with code ${code}`));
            }
        });
    });
}

async function ensureWhatsAppRuntime() {
    const whatsappDir = path.join(__dirname, 'whatsapp');
    const nodeModules = path.join(whatsappDir, 'node_modules');
    const npmCmd = resolveNpmExecutable();

    if (!fs.existsSync(nodeModules)) {
        await runSetupCommand(npmCmd, ['install'], whatsappDir, 'Installing WhatsApp npm dependencies');
    } else {
        console.log('[setup] WhatsApp npm dependencies already installed');
    }

    await runSetupCommand(
        npmCmd,
        ['run', 'install:browser'],
        whatsappDir,
        'Installing Puppeteer Chrome binary'
    );
}

function startBot(botConfig) {
    console.log(`Starting ${botConfig.name}...`);

    const proc = spawn(botConfig.cmd, botConfig.args, {
        cwd: botConfig.cwd,
        env: botConfig.env,
        stdio: 'inherit',
        shell: false,
    });

    proc.on('error', (err) => {
        console.error(`${botConfig.name} error:`, err);
    });

    proc.on('close', (code) => {
        console.warn(`${botConfig.name} exited with code ${code}`);
        console.log(`Restarting ${botConfig.name}...`);
        setTimeout(() => startBot(botConfig), 3000);
    });

    activeProcesses.push(proc);
    console.log(`${botConfig.name} started (PID: ${proc.pid})\n`);
}

async function main() {
    console.log('\n' + '='.repeat(60));
    console.log('FOOTBALL BOT MULTI-LAUNCHER');
    console.log('='.repeat(60) + '\n');
    console.log(`[setup] Puppeteer cache dir: ${whatsappCacheDir}`);

    try {
        await ensureWhatsAppRuntime();
    } catch (error) {
        console.error(`Setup failed: ${error.message}`);
        process.exit(1);
    }

    const bots = [
        {
            name: 'API Server',
            cwd: path.join(__dirname, '..'),
            cmd: resolvePythonExecutable(),
            args: ['run_api.py'],
            env: { ...process.env },
        },
        {
            name: 'WhatsApp Bot',
            cwd: path.join(__dirname, 'whatsapp'),
            cmd: 'node',
            args: ['bot.js'],
            env: { ...process.env },
        },
        {
            name: 'Telegram Bot',
            cwd: path.join(__dirname, '..'),
            cmd: resolvePythonExecutable(),
            args: ['-m', 'frontend.telegram'],
            env: { ...process.env },
        },
    ];

    bots.forEach((bot) => startBot(bot));

    console.log('='.repeat(60));
    console.log('All services are running');
    console.log('='.repeat(60));
    console.log('\nAPI Server: http://localhost:8000');
    console.log('WhatsApp: Scan QR code in the terminal/browser window');
    console.log('Telegram: @YourBotName\n');
}

process.on('SIGINT', () => {
    console.log('\n\nShutting down...');
    activeProcesses.forEach((proc) => {
        if (proc && !proc.killed) {
            proc.kill();
        }
    });
    process.exit(0);
});

main();
