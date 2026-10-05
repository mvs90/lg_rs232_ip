"""Install the optional HA automation template without overwriting user files."""

from pathlib import Path


def install_blueprint(config_dir):
    destination = Path(config_dir) / "blueprints/automation/lg_rs232_ip/event_view.yaml"
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("xb") as output:
            output.write(
                (Path(__file__).parent / "blueprints/event_view.yaml").read_bytes()
            )
    except FileExistsError:
        pass
