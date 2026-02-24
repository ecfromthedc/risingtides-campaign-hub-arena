"""Campaign Manager Flask application factory."""
from flask import Flask
from flask_cors import CORS

from campaign_manager.config import Config
from campaign_manager import db


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    # Initialize CORS
    CORS(app, origins=app.config["CORS_ORIGINS"])

    # Initialize database
    db.init(app.config.get("DATABASE_URL"))

    from campaign_manager.blueprints.health import health_bp
    from campaign_manager.blueprints.campaigns import campaigns_bp
    from campaign_manager.blueprints.internal import internal_bp
    from campaign_manager.blueprints.inbox import inbox_bp
    from campaign_manager.blueprints.webhooks import webhooks_bp
    from campaign_manager.blueprints.migrate import migrate_bp
    from campaign_manager.blueprints.slack_events import slack_events_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(internal_bp)
    app.register_blueprint(inbox_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(migrate_bp)
    app.register_blueprint(slack_events_bp)

    # Initialize Slack bot (no-op if credentials aren't set)
    if app.config.get("SLACK_BOT_TOKEN"):
        from campaign_manager.services.slack_bot import init_slack_app
        init_slack_app()

    return app
