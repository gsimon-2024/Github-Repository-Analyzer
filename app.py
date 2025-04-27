from flask import Flask, render_template, request, redirect, url_for, flash
import requests
from urllib.parse import urlparse
import os
import time
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # For flashing messages

@app.template_filter('timestamp')
def timestamp_filter(timestamp):
    """Convert Unix timestamp to datetime"""
    return datetime.fromtimestamp(timestamp)

@app.template_filter('strftime')
def strftime_filter(date, format='%Y-%m-%d'):
    """Format a date using strftime"""
    return date.strftime(format)

GITHUB_API = 'https://api.github.com'
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

def get_headers(token=None):
    """Get headers for GitHub API requests"""
    headers = {'Accept': 'application/vnd.github.v3+json'}
    if token:
        headers['Authorization'] = f'token {token}'
    elif GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    return headers

def retry_on_ratelimit(max_retries=3, initial_delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries):
                response, status_code = func(*args, **kwargs)
                
                if status_code != 403 or 'rate limit exceeded' not in str(response.get('message', '')).lower():
                    return response, status_code
                
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                
            return response, status_code
        return wrapper
    return decorator

def parse_github_url(url):
    """Parse GitHub URL to get owner and repo name"""
    try:
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split('/') if p]
        if len(path_parts) >= 2:
            return path_parts[0], path_parts[1]
    except Exception as e:
        app.logger.error(f'Error parsing GitHub URL: {e}')
    return None, None

def get_default_dates():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

@app.route('/', methods=['GET', 'POST'])
def index():
    default_start, default_end = get_default_dates()
    context = {
        'start_date': default_start,
        'end_date': default_end
    }
    
    if request.method == 'POST':
        repo_url = request.form.get('repo_url')
        github_token = request.form.get('github_token')
        start_date = request.form.get('start_date') or default_start
        end_date = request.form.get('end_date') or default_end
        
        context.update({
            'repo_url': repo_url,
            'github_token': github_token,
            'start_date': start_date,
            'end_date': end_date
        })
        
        owner, repo = parse_github_url(repo_url)
        if not owner or not repo:
            flash('Invalid GitHub repository URL.', 'danger')
            return render_template('index.html', **context)

        try:
            # Get repository info
            headers = get_headers(github_token)
            repo_response = requests.get(f'{GITHUB_API}/repos/{owner}/{repo}', headers=headers)
            if repo_response.status_code != 200:
                flash('Error fetching repository information. Please check the URL and try again.', 'danger')
                return render_template('index.html', **context)

            repo_data = repo_response.json()
            context['repo'] = repo_data

            # Convert dates to datetime objects for comparison
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            # Fetch commits for the specific date range
            commit_activity = []
            page = 1
            per_page = 100
            weekly_commits = {}
            
            while True:
                commits_url = f'{GITHUB_API}/repos/{owner}/{repo}/commits'
                params = {
                    'since': f'{start_date}T00:00:00Z',
                    'until': f'{end_date}T23:59:59Z',
                    'per_page': per_page,
                    'page': page
                }
                
                commit_response = requests.get(commits_url, headers=headers, params=params)
                
                if commit_response.status_code != 200:
                    flash('Error fetching commit activity. Please check the repository URL.', 'warning')
                    break
                
                commits = commit_response.json()
                if not commits:
                    break
                
                # Group commits by week
                for commit in commits:
                    commit_date = datetime.strptime(commit['commit']['author']['date'], '%Y-%m-%dT%H:%M:%SZ')
                    # Get the start of the week (Monday)
                    week_start = commit_date - timedelta(days=commit_date.weekday())
                    week_key = week_start.strftime('%Y-%m-%d')
                    
                    if week_key not in weekly_commits:
                        weekly_commits[week_key] = {
                            'week': int(week_start.timestamp()),
                            'total': 0
                        }
                    weekly_commits[week_key]['total'] += 1
                
                if len(commits) < per_page:
                    break
                page += 1
            
            # Convert weekly commits to list and calculate stats
            commit_activity = list(weekly_commits.values())
            total_commits = sum(week['total'] for week in commit_activity)
            weeks_count = len(commit_activity)
            avg_commits_per_week = total_commits / weeks_count if weeks_count > 0 else 0
            context['avg_commits_per_week'] = avg_commits_per_week

            # Get contributors (optional)
            contrib_response = requests.get(f'{GITHUB_API}/repos/{owner}/{repo}/contributors', headers=headers)
            contributors = contrib_response.json() if contrib_response.status_code == 200 else []
            context['contributors'] = contributors
            
            if contrib_response.status_code != 200:
                flash('Error fetching contributors. Some data might be incomplete.', 'warning')

            # Process commit activity
            weekly_commits = []
            if isinstance(commit_activity, list):
                for week in commit_activity:
                    try:
                        week_timestamp = week.get('week', 0)
                        if not week_timestamp:
                            continue
                        week_start = time.strftime('%Y-%m-%d', time.gmtime(week_timestamp))
                        if week_start < start_date:
                            continue
                        if week_start > end_date:
                            continue
                        weekly_commits.append(week.get('total', 0))
                    except (TypeError, AttributeError) as e:
                        app.logger.error(f'Error processing week data: {e}')
                        continue

            if not weekly_commits:
                if start_date or end_date:
                    flash(f'No commit activity found in the selected date range ({start_date or "beginning"} to {end_date or "now"}).', 'info')
                else:
                    flash('No commit activity found in the last 52 weeks. This could mean the repository is inactive or was recently created.', 'info')
                avg_commits_per_week = 0
            else:
                avg_commits_per_week = sum(weekly_commits) / len(weekly_commits)
            
            context.update({
                'commit_activity': commit_activity,
                'avg_commits_per_week': avg_commits_per_week
            })

            # Check rate limit status
            rate_limit = requests.get(f'{GITHUB_API}/rate_limit', headers=headers).json()
            remaining = rate_limit.get('resources', {}).get('core', {}).get('remaining', 0)
            reset_time = rate_limit.get('resources', {}).get('core', {}).get('reset', 0)
            reset_minutes = max(0, int((reset_time - time.time()) / 60))
            
            if not (GITHUB_TOKEN or github_token):
                flash('Running in unauthenticated mode. Rate limits are restricted to 60 requests per hour. Add a GitHub token to increase this limit.', 'warning')
            
            if remaining < 100:
                flash(f'GitHub API rate limit is running low: {remaining} requests remaining. Resets in {reset_minutes} minutes.', 'warning')

        except Exception as e:
            app.logger.error(f'Error processing request: {e}')
            flash(f'An error occurred while processing your request: {str(e)}', 'danger')


        

        

    return render_template('index.html', **context)

if __name__ == '__main__':
    app.run(debug=True)
