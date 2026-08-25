"""CLI entry point for the autonomous buyer agent."""

import argparse
import asyncio
import logging
import signal
import sys

from agent.buyer import AutonomousBuyer

def setup_logging() -> None:
    """Configure basic logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run the Autonomous Buyer Agent')
    parser.add_argument('--base-url', type=str, default='http://localhost:8000', help='Backend base URL')
    parser.add_argument('--cycles', type=int, default=None, help='Max number of cycles to run (infinite by default)')
    parser.add_argument('--interval', type=int, default=10, help='Polling interval in seconds')
    parser.add_argument('--max-failures', type=int, default=3, help='Max consecutive failures before shutdown')
    
    args = parser.parse_args()
    
    setup_logging()
    
    buyer = AutonomousBuyer(
        base_url=args.base_url,
        poll_interval=args.interval,
        max_failures=args.max_failures
    )
    
    def handle_signal(sig, frame):
        print(f"\nReceived signal {sig}. Initiating graceful shutdown...")
        buyer.request_shutdown()
        
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    print('Starting Autonomous Buyer Agent...')
    print('Press Ctrl+C to initiate graceful shutdown.')
    
    try:
        asyncio.run(buyer.run(max_cycles=args.cycles))
    except KeyboardInterrupt:
        pass
    print("Agent shut down successfully.")

if __name__ == '__main__':
    main()
