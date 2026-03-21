#!/usr/bin/env node

/**
 * WhatsApp Bot Launcher
 * Installs dependencies, ensures Puppeteer browser binary, then starts the bot.
 */

import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const nodeModulesPath = path.join(__dirname, 'node_modules');
const puppeteerCacheDir = process.env.PUPPETEER_CACHE_DIR || path.join(__dirname, '.cache', 'puppeteer');

fs.mkdirSync(puppeteerCacheDir, { recursive: true });
process.env.PUPPETEER_CACHE_DIR = puppeteerCacheDir;

function runCommand(command, args, cwd) {
    return new Promise((resolve, reject) => {
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
        });

        proc.on('close', (code) => {
            if (code === 0) {
                resolve();
            } else {
                reject(new Error(`Command failed with code ${code}`));
            }
        });

        proc.on('error', (error) => reject(error));
    });
}

function resolveNpmExecutable() {
    return process.platform === 'win32' ? 'npm.cmd' : 'npm';
}

async function main() {
    try {
        const npmCmd = resolveNpmExecutable();
        console.log('WhatsApp Bot Launcher\n');
        console.log(`Puppeteer cache dir: ${puppeteerCacheDir}\n`);

        if (!fs.existsSync(nodeModulesPath)) {
            console.log('Installing dependencies...');
            await runCommand(npmCmd, ['install'], __dirname);
            console.log('Dependencies installed\n');
        } else {
            console.log('Dependencies already installed\n');
        }

        console.log('Ensuring Puppeteer browser binary is installed...');
        await runCommand(npmCmd, ['run', 'install:browser'], __dirname);
        console.log('Puppeteer browser ready\n');

        console.log('Starting WhatsApp bot...\n');
        await runCommand('node', ['bot.js'], __dirname);
    } catch (error) {
        console.error('Error:', error.message);
        process.exit(1);
    }
}

main();
