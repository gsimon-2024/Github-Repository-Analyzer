# GitHub Repo Analyzer

A Flask web app to analyze public GitHub repositories and present insights using the GitHub API.

## Features
- Input field for GitHub repo link
- Fetch and display repo metadata (name, stars, forks, etc.)
- Display contributor and commit activity data
- Handles rate-limiting with exponential backoff
- Shows commit frequency metrics
- Docker support for easy deployment

## Running with Docker (Recommended)

### Using Docker Compose (Easiest)

1. Build and run the container:
   ```bash
   docker-compose up --build
   ```

2. Access the application at [http://localhost:5000](http://localhost:5000)

3. (Optional) Set your GitHub token:
   - Open docker-compose.yml
   - Uncomment the GITHUB_TOKEN line
   - Replace 'your_token_here' with your actual GitHub token
   - Restart the container

### Using Docker Directly

1. Build the image:
   ```bash
   docker build -t github-repo-analyzer .
   ```

2. Run the container:
   ```bash
   docker run -p 5000:5000 -e GITHUB_TOKEN=your_token_here github-repo-analyzer
   ```

   Note: Replace 'your_token_here' with your GitHub token or omit the -e flag to run without a token.
   ```bash
   docker run -p 5000:5000 github-repo-analyzer
   ```

## Manual Installation (Alternative)

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the app:
   ```bash
   python app.py
   ```

3. Open your browser at [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Rate Limits

- Without authentication: 60 requests per hour
- With GitHub token: 5,000 requests per hour

To increase rate limits, set your GitHub token in the docker-compose.yml file or as an environment variable.
