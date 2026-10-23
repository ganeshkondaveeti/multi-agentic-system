import pino from 'pino';
import { config } from '../config.js';

// Logs go to stderr: under the stdio transport, stdout carries the MCP protocol.
export const logger =
  config.nodeEnv !== 'production'
    ? pino({
        level: config.logging.level,
        transport: {
          target: 'pino-pretty',
          options: {
            colorize: true,
            destination: 2,
          },
        },
      })
    : pino({ level: config.logging.level }, pino.destination(2));
