#!/usr/bin/env node

/**
 * Ensures Puppeteer Chrome binary is installed for whatsapp-web.js runtime.
 * This is intended for server environments where system Chrome may not exist.
 */

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const projectDir = __dirname;
const skipDownload = String(process.env.PUPPETEER_SKIP_DOWNLOAD || '').toLowerCase() === 'true';
const cacheDir = process.env.PUPPETEER_CACHE_DIR || path.join(projectDir, '.cache', 'puppeteer');
const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';

if (skipDownload) {
    console.log('PUPPETEER_SKIP_DOWNLOAD=true -> skipping browser download.');
    process.exit(0);
}

fs.mkdirSync(cacheDir, { recursive: true });
const installEnv = { ...process.env, PUPPETEER_CACHE_DIR: cacheDir };
console.log(`Using Puppeteer cache directory: ${cacheDir}`);

function runAttempt(attempt) {
    if (attempt.requirePath && !fs.existsSync(attempt.requirePath)) {
        console.log(`Skipping ${attempt.label}: ${attempt.requirePath} not found.`);
        return { status: 1, skipped: true };
    }

    console.log(`Ensuring Puppeteer Chrome binary is installed (${attempt.label})...`);
    let spawnCommand = attempt.command;
    let spawnArgs = attempt.args;

    if (process.platform === 'win32' && String(attempt.command).toLowerCase().endsWith('.cmd')) {
        const commandLine = [attempt.command, ...attempt.args].join(' ');
        spawnCommand = process.env.ComSpec || 'cmd.exe';
        spawnArgs = ['/d', '/s', '/c', commandLine];
    }

    const result = spawnSync(spawnCommand, spawnArgs, {
        cwd: projectDir,
        stdio: 'inherit',
        shell: false,
        env: installEnv,
    });

    if (result.error) {
        console.error(`Installer process error (${attempt.label}): ${result.error.message}`);
    }
    return result;
}

const localPuppeteerCli = path.join(
    projectDir,
    'node_modules',
    'puppeteer',
    'lib',
    'cjs',
    'puppeteer',
    'node',
    'cli.js'
);

const localBrowsersCli = path.join(
    projectDir,
    'node_modules',
    '@puppeteer',
    'browsers',
    'lib',
    'cjs',
    'main-cli.js'
);

const attempts = [
    {
        label: 'via local puppeteer CLI',
        command: process.execPath,
        args: [localPuppeteerCli, 'install', 'chrome'],
        requirePath: localPuppeteerCli,
    },
    {
        label: 'via local @puppeteer/browsers CLI',
        command: process.execPath,
        args: [localBrowsersCli, 'install', 'chrome@stable'],
        requirePath: localBrowsersCli,
    },
    {
        label: 'via npm puppeteer CLI',
        command: npmCmd,
        args: ['exec', '--yes', '--package', 'puppeteer', '--', 'puppeteer', 'install', 'chrome'],
    },
    {
        label: 'via npm @puppeteer/browsers CLI',
        command: npmCmd,
        args: ['exec', '--yes', '--package', '@puppeteer/browsers', '--', 'browsers', 'install', 'chrome@stable'],
    },
];

let lastResult = { status: 1 };
for (const attempt of attempts) {
    lastResult = runAttempt(attempt);
    if (lastResult.status === 0) {
        console.log('Puppeteer Chrome binary is ready.');
        process.exit(0);
    }
}

const exitCode = typeof lastResult.status === 'number' ? lastResult.status : 1;
console.error(`Failed to install Puppeteer Chrome binary (exit code: ${exitCode}).`);
console.error(
    'Manual fallback: run `set PUPPETEER_CACHE_DIR=.cache\\\\puppeteer && npm exec --yes --package puppeteer -- puppeteer install chrome` ' +
        'inside frontend/whatsapp.'
);
process.exit(exitCode);
