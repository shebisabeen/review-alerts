#!/usr/bin/env python3
"""
Main Review Monitor
Runs both Reddit and Trustpilot monitoring scripts
"""

import os
import sys
import subprocess
import logging
from datetime import datetime
from pathlib import Path
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('main_monitor.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('MainMonitor')

class ReviewMonitor:
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.reddit_script = self.script_dir / "monitor_reddit.py"
        self.trustpilot_script = self.script_dir / "monitor_trustpilot.py"
        self.playstore_script = self.script_dir / "monitor_playstore.py"
        
    def check_script_exists(self, script_path):
        """Check if script file exists"""
        if not script_path.exists():
            logger.error(f"Script not found: {script_path}")
            return False
        return True
    
    def should_run_script(self, script_name):
        """Check if the script should be run based on environment variable"""
        env_var = f"RUN_{script_name.upper()}"
        return os.environ.get(env_var, "true").lower() == "true"
    
    
    def run_script(self, script_path, script_name):
        """Run a monitoring script and return the result"""
        logger.info(f"Starting {script_name} monitoring...")
        
        try:
            # Run the script
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            if result.returncode == 0:
                logger.info(f"✅ {script_name} monitoring completed successfully")
                if result.stdout:
                    logger.info(f"{script_name} output:\n{result.stdout}")
            else:
                logger.error(f"❌ {script_name} monitoring failed with return code {result.returncode}")
                if result.stderr:
                    logger.error(f"{script_name} error:\n{result.stderr}")
                if result.stdout:
                    logger.info(f"{script_name} output:\n{result.stdout}")
            
            return result.returncode
            
        except subprocess.TimeoutExpired:
            logger.error(f"⏰ {script_name} monitoring timed out after 10 minutes")
            return 1
        except Exception as e:
            logger.error(f"💥 Exception running {script_name} monitoring: {e}")
            return 1
    
    def run_all_monitors(self):
        """Run all monitoring scripts"""
        logger.info("=" * 60)
        logger.info("🚀 Starting Review Alert Monitoring Suite")
        logger.info(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        results = {}
        
        # Check if scripts exist
        scripts_to_run = []
        
        if self.check_script_exists(self.reddit_script) and self.should_run_script("Reddit"):
            scripts_to_run.append((self.reddit_script, "Reddit"))
        
        if self.check_script_exists(self.trustpilot_script) and self.should_run_script("Trustpilot"):
            scripts_to_run.append((self.trustpilot_script, "Trustpilot"))
        
        if self.check_script_exists(self.playstore_script) and self.should_run_script("Playstore"):
            scripts_to_run.append((self.playstore_script, "Playstore"))
        
        if not scripts_to_run:
            logger.error("❌ No monitoring scripts found!")
            return 1
        
        # Run each script
        for script_path, script_name in scripts_to_run:
            start_time = datetime.now()
            
            logger.info(f"\n📊 Running {script_name} Monitor")
            logger.info("-" * 40)
            
            return_code = self.run_script(script_path, script_name)
            results[script_name] = return_code
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(f"⏱️  {script_name} monitoring took {duration:.1f} seconds")
            
            # Small delay between scripts
            if len(scripts_to_run) > 1:
                logger.info("⏸️  Waiting 5 seconds before next script...")
                time.sleep(5)
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("📋 MONITORING SUMMARY")
        logger.info("=" * 60)
        
        all_success = True
        for script_name, return_code in results.items():
            status = "✅ SUCCESS" if return_code == 0 else "❌ FAILED"
            logger.info(f"{script_name:<15}: {status}")
            if return_code != 0:
                all_success = False
        
        final_status = "✅ ALL MONITORS COMPLETED SUCCESSFULLY" if all_success else "⚠️  SOME MONITORS FAILED"
        logger.info(f"\n{final_status}")
        logger.info(f"🏁 Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        return 0 if all_success else 1

def main():
    """Main function"""
    try:
        monitor = ReviewMonitor()
        return monitor.run_all_monitors()
    except KeyboardInterrupt:
        logger.info("\n⚠️  Monitoring interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"💥 Unexpected error in main monitor: {e}")
        return 1

if __name__ == "__main__":
    exit(main())