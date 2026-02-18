import logging
import os

def setup_agent_logging(agent_name: str, log_level=logging.INFO, log_dir="logs"):
    """
    Sets up standardized logging for agents.

    Args:
        agent_name (str): The name of the agent for identifying logs.
        log_level (int): The logging level (e.g., logging.INFO, logging.DEBUG).
        log_dir (str): Directory to store log files.
    """
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{agent_name}.log")

    # Create logger
    logger = logging.getLogger(agent_name)
    logger.setLevel(log_level)

    # Prevent adding multiple handlers if already set up
    if not logger.handlers:
        # Create file handler which logs even debug messages
        fh = logging.FileHandler(log_file)
        fh.setLevel(log_level)

        # Create console handler with a higher log level
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING) # Only show warnings/errors in console by default

        # Create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        # Add the handlers to the logger
        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger

if __name__ == "__main__":
    # Example usage:
    # Keep side effects minimal; this module is meant to be imported by agents.
    pass
