"""Plugin entry point. Keep the launcher usable as a standalone script too."""
def register(ctx):
    from .launcher import launch, setup_parser

    ctx.register_cli_command(
        "fast-chat", "Start a model-specific Fast session", setup_parser, launch,
    )
