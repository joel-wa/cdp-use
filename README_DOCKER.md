# Docker Support for CDP Browser MCP

This project includes Docker support for running the CDP Browser MCP server in a containerized environment.
Two Dockerfiles are provided: one using Chromium and another using Google Chrome.

## Prerequisites

- Docker installed on your machine.

## Building the Images

### Option 1: Chromium (Recommended for size/speed)

```bash
docker build -f Dockerfile.chromium -t cdp-use-chromium .
```

### Option 2: Google Chrome

```bash
docker build -f Dockerfile.chrome -t cdp-use-chrome .
```

## Running the Container

To run the container and expose the Chrome debugging port (9222):

```bash
docker run -it --rm -p 9222:9222 cdp-use-chromium
```

Or for the Chrome version:

```bash
docker run -it --rm -p 9222:9222 cdp-use-chrome
```

## Environment Variables

The Dockerfiles set the following environment variables automatically:

- `GOOGLE_CHROME_PATH`: Path to the browser executable.
- `USER_PROFILE_PATH`: Path to the user profile directory inside the container.
- `CHROME_ARGS`: Additional arguments for Chrome (default: `--no-sandbox --headless=new --disable-gpu --disable-dev-shm-usage`).

You can override these when running the container:

```bash
docker run -it --rm -e CHROME_ARGS="--no-sandbox --headless=new" cdp-use-chromium
```

## Notes

- The container runs Chrome in headless mode by default.
- The MCP server communicates via stdin/stdout, so running with `-it` allows you to interact with it if you are piping input, but typically you would connect an MCP client to the container's stdio.
- If you need to see the browser UI, you would need to set up X11 forwarding or use a VNC-enabled base image, which is outside the scope of these basic Dockerfiles.
