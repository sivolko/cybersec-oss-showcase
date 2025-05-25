#!/usr/bin/env python3
"""
Cybersecurity OSS Showcase Scraper
Automatically fetches GitHub metrics for cybersecurity tools
"""

import os
import sys
import yaml
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any
import time
from pathlib import Path

class GitHubScraper:
    def __init__(self, github_token: str = None):
        self.github_token = github_token or os.environ.get('GITHUB_TOKEN')
        self.session = requests.Session()
        
        if self.github_token:
            self.session.headers.update({
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'cybersec-oss-showcase-scraper/1.0'
            })
        
        self.base_url = 'https://api.github.com'
        self.rate_limit_remaining = 5000
        
    def get_repo_data(self, repo_name: str) -> Dict[str, Any]:
        """Fetch comprehensive data for a GitHub repository"""
        
        if self.rate_limit_remaining < 10:
            print(f"⚠️ Rate limit low ({self.rate_limit_remaining}), sleeping...")
            time.sleep(60)
            
        url = f"{self.base_url}/repos/{repo_name}"
        
        try:
            response = self.session.get(url)
            self.rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            
            if response.status_code == 404:
                print(f"❌ Repository not found: {repo_name}")
                return None
                
            if response.status_code != 200:
                print(f"❌ Error fetching {repo_name}: {response.status_code}")
                return None
                
            data = response.json()
            
            # Get additional data
            releases_data = self.get_latest_release(repo_name)
            contributors_count = self.get_contributors_count(repo_name)
            
            return {
                'name': data['name'],
                'full_name': data['full_name'],
                'description': data['description'] or 'No description available',
                'homepage': data['homepage'],
                'stars': data['stargazers_count'],
                'forks': data['forks_count'],
                'watchers': data['watchers_count'],
                'open_issues': data['open_issues_count'],
                'language': data['language'],
                'created_at': data['created_at'],
                'updated_at': data['updated_at'],
                'pushed_at': data['pushed_at'],
                'size': data['size'],
                'default_branch': data['default_branch'],
                'archived': data['archived'],
                'disabled': data['disabled'],
                'license': data['license']['name'] if data['license'] else None,
                'topics': data['topics'],
                'has_wiki': data['has_wiki'],
                'has_pages': data['has_pages'],
                'has_discussions': data['has_discussions'],
                'latest_release': releases_data,
                'contributors_count': contributors_count,
                'last_commit_days_ago': self.days_since_last_commit(data['pushed_at']),
                'health_score': self.calculate_health_score(data, contributors_count)
            }
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error fetching {repo_name}: {e}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error fetching {repo_name}: {e}")
            return None
    
    def get_latest_release(self, repo_name: str) -> Dict[str, Any]:
        """Get latest release information"""
        url = f"{self.base_url}/repos/{repo_name}/releases/latest"
        
        try:
            response = self.session.get(url)
            if response.status_code == 200:
                data = response.json()
                return {
                    'tag_name': data['tag_name'],
                    'name': data['name'],
                    'published_at': data['published_at'],
                    'prerelease': data['prerelease']
                }
        except:
            pass
        
        return None
    
    def get_contributors_count(self, repo_name: str) -> int:
        """Get approximate number of contributors"""
        url = f"{self.base_url}/repos/{repo_name}/contributors"
        
        try:
            response = self.session.get(url, params={'per_page': 1, 'anon': 'true'})
            if response.status_code == 200:
                # Get total from Link header
                link_header = response.headers.get('Link', '')
                if 'rel="last"' in link_header:
                    # Extract page number from last page link
                    import re
                    match = re.search(r'page=(\d+)>; rel="last"', link_header)
                    if match:
                        return int(match.group(1))
                
                # Fallback: count items in response
                return len(response.json())
        except:
            pass
        
        return 0
    
    def days_since_last_commit(self, pushed_at: str) -> int:
        """Calculate days since last commit"""
        try:
            last_commit = datetime.fromisoformat(pushed_at.replace('Z', '+00:00'))
            now = datetime.now(last_commit.tzinfo)
            return (now - last_commit).days
        except:
            return -1
    
    def calculate_health_score(self, repo_data: Dict, contributors_count: int) -> float:
        """Calculate a health score for the repository (0-100)"""
        score = 0
        
        # Stars (max 30 points)
        stars = repo_data['stargazers_count']
        if stars >= 10000:
            score += 30
        elif stars >= 1000:
            score += 20 + (stars - 1000) / 900 * 10
        elif stars >= 100:
            score += 10 + (stars - 100) / 900 * 10
        else:
            score += stars / 100 * 10
        
        # Recent activity (max 25 points)
        days_since_commit = self.days_since_last_commit(repo_data['pushed_at'])
        if days_since_commit <= 7:
            score += 25
        elif days_since_commit <= 30:
            score += 20
        elif days_since_commit <= 90:
            score += 15
        elif days_since_commit <= 365:
            score += 10
        else:
            score += 5
        
        # Contributors (max 20 points)
        if contributors_count >= 100:
            score += 20
        elif contributors_count >= 50:
            score += 15
        elif contributors_count >= 10:
            score += 10
        elif contributors_count >= 1:
            score += 5
        
        # Issues management (max 15 points)
        if repo_data['open_issues_count'] < 50:
            score += 15
        elif repo_data['open_issues_count'] < 200:
            score += 10
        else:
            score += 5
        
        # Documentation and community (max 10 points)
        if repo_data['has_wiki']:
            score += 3
        if repo_data['has_pages']:
            score += 3
        if repo_data['license']:
            score += 2
        if len(repo_data['topics']) > 0:
            score += 2
        
        return min(score, 100)
    
    def format_number(self, num: int) -> str:
        """Format large numbers with k/M suffixes"""
        if num >= 1000000:
            return f"{num/1000000:.1f}M"
        elif num >= 1000:
            return f"{num/1000:.1f}k"
        else:
            return str(num)
    
    def format_time_ago(self, days: int) -> str:
        """Format days ago into human readable format"""
        if days < 0:
            return "Unknown"
        elif days == 0:
            return "Today"
        elif days == 1:
            return "1 day ago"
        elif days < 7:
            return f"{days} days ago"
        elif days < 30:
            weeks = days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        elif days < 365:
            months = days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        else:
            years = days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"

def load_tools_config() -> Dict[str, List[Dict]]:
    """Load tools configuration from YAML file"""
    config_path = Path(__file__).parent.parent / 'data' / 'tools.yaml'
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"❌ Configuration file not found: {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"❌ Error parsing YAML: {e}")
        sys.exit(1)

def save_data(data: Dict, filename: str):
    """Save data to JSON file"""
    output_dir = Path(__file__).parent.parent / 'data'
    output_dir.mkdir(exist_ok=True)
    
    with open(output_dir / filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def generate_readme(tools_data: Dict[str, List[Dict]]) -> str:
    """Generate updated README.md content"""
    scraper = GitHubScraper()
    
    # Calculate statistics
    total_tools = sum(len(tools) for tools in tools_data.values())
    total_stars = sum(sum(tool.get('stars', 0) for tool in tools) for tools in tools_data.values())
    
    # Category mappings
    category_mapping = {
        'vulnerability_scanners': '🔍 Vulnerability Scanners',
        'security_automation': '🤖 Security Automation',
        'threat_intelligence': '🕵️ Threat Intelligence',
        'container_security': '📦 Container Security',
        'cloud_security': '☁️ Cloud Security Tools',
        'devsecops': '🔧 DevSecOps',
        'incident_response': '🚨 Incident Response',
        'penetration_testing': '🎯 Penetration Testing',
        'cryptography': '🔒 Cryptography',
        'security_learning': '📚 Security Learning'
    }
    
    readme = f"""# 🔐 Cybersecurity OSS Showcase

> A curated collection of the best open source cybersecurity tools, automatically updated with real-time GitHub metrics.

[![Auto Update](https://github.com/sivolko/cybersec-oss-showcase/actions/workflows/update-data.yml/badge.svg)](https://github.com/sivolko/cybersec-oss-showcase/actions/workflows/update-data.yml)
[![Last Updated](https://img.shields.io/badge/last%20updated-{datetime.now().strftime('%Y--%m--%d')}-brightgreen.svg)](https://github.com/sivolko/cybersec-oss-showcase)

## 📊 Dashboard Overview

- **Total Tools Tracked**: {total_tools}
- **Categories**: {len(tools_data)}
- **Auto-Updated**: Every 6 hours
- **Last Scan**: {datetime.now().strftime('%Y-%m-%d')}
- **Total Community**: {scraper.format_number(total_stars)}+ stars

## 🗂️ Categories

| Category | Tools | Top Tool | Stars |
|----------|-------|----------|---------|
"""
    
    # Add category overview table
    for category_key, tools in tools_data.items():
        if not tools:
            continue
            
        category_name = category_mapping.get(category_key, category_key.replace('_', ' ').title())
        tool_count = len(tools)
        
        # Find top tool by stars
        top_tool = max(tools, key=lambda x: x.get('stars', 0), default={})
        top_tool_name = top_tool.get('name', 'N/A')
        top_tool_stars = scraper.format_number(top_tool.get('stars', 0))
        
        readme += f"| [{category_name}](#{category_key.replace('_', '-')}) | {tool_count} | {top_tool_name} | {top_tool_stars} ⭐ |\n"
    
    readme += "\n---\n\n"
    
    # Add detailed sections for each category
    for category_key, tools in tools_data.items():
        if not tools:
            continue
            
        category_name = category_mapping.get(category_key, category_key.replace('_', ' ').title())
        
        # Add category description
        descriptions = {
            'vulnerability_scanners': 'Tools for discovering security vulnerabilities in applications, networks, and infrastructure',
            'security_automation': 'Automation frameworks and tools for security operations',
            'threat_intelligence': 'Tools for threat hunting, intelligence gathering, and analysis',
            'container_security': 'Security tools specifically designed for containers and Kubernetes',
            'cloud_security': 'Security tools for cloud environments (AWS, Azure, GCP)',
            'devsecops': 'Tools for integrating security into development workflows',
            'incident_response': 'Tools for digital forensics and incident response',
            'penetration_testing': 'Tools for ethical hacking and penetration testing',
            'cryptography': 'Libraries and tools for cryptographic operations',
            'security_learning': 'Educational resources, CTFs, and learning platforms'
        }
        
        description = descriptions.get(category_key, '')
        
        readme += f"## {category_name}\n\n"
        if description:
            readme += f"> {description}\n\n"
        
        readme += "| Tool | Description | Stars | Language | Last Commit | Health |\n"
        readme += "|------|-------------|-------|----------|-------------|--------|\n"
        
        # Sort tools by stars (descending)
        sorted_tools = sorted(tools, key=lambda x: x.get('stars', 0), reverse=True)
        
        for tool in sorted_tools[:10]:  # Show top 10 tools per category
            name = tool.get('name', 'Unknown')
            repo = tool.get('full_name', '')
            description = tool.get('description', 'No description')[:80] + ('...' if len(tool.get('description', '')) > 80 else '')
            stars = scraper.format_number(tool.get('stars', 0))
            language = tool.get('language', 'Unknown')
            last_commit = scraper.format_time_ago(tool.get('last_commit_days_ago', -1))
            health_score = tool.get('health_score', 0)
            
            # Health indicator
            if health_score >= 80:
                health_indicator = "🟢"
            elif health_score >= 60:
                health_indicator = "🟡"
            else:
                health_indicator = "🔴"
            
            readme += f"| [{name}](https://github.com/{repo}) | {description} | {stars} ⭐ | {language} | {last_commit} | {health_indicator} |\n"
        
        readme += "\n"
    
    # Add trending section
    readme += """## 📈 Trending This Week

<!-- AUTO-GENERATED: This section is updated by GitHub Actions -->

🔥 **Most Active Projects:**

"""
    
    # Find most recently updated tools
    all_tools = []
    for tools in tools_data.values():
        all_tools.extend(tools)
    
    recently_active = sorted(all_tools, key=lambda x: x.get('last_commit_days_ago', 999))
    
    for i, tool in enumerate(recently_active[:5], 1):
        name = tool.get('name', 'Unknown')
        repo = tool.get('full_name', '')
        days_ago = tool.get('last_commit_days_ago', -1)
        stars = scraper.format_number(tool.get('stars', 0))
        readme += f"{i}. **[{name}](https://github.com/{repo})** ({stars} ⭐) - Last updated {scraper.format_time_ago(days_ago)}\n"
    
    readme += """\n## 🤖 Automation

This showcase is automatically updated every 6 hours using GitHub Actions. The scraper:

- ✅ Fetches latest GitHub metrics (stars, forks, last commit)
- ✅ Checks for new releases and updates
- ✅ Monitors tool activity and health
- ✅ Updates popularity rankings
- ✅ Calculates health scores for projects

## 🎯 How to Contribute

### Add a New Tool

1. Edit `data/tools.yaml`
2. Add your tool under the appropriate category:

```yaml
category_name:
  - name: "your-tool"
    repo: "owner/repo-name"
    description: "Brief description"
    homepage: "https://tool-website.com" # optional
```

3. Create a pull request
4. The scraper will automatically fetch GitHub metrics

---

**🤝 Maintained by [@myselfshubhendu](https://twitter.com/myselfshubhendu)**

*Inspired by Tom Dörr's [Repository Showcase](https://tom-doerr.github.io/repo_posts/)*

**⭐ Star this repo to stay updated with the latest cybersecurity tools!**
"""
    
    return readme

def main():
    """Main scraper function"""
    print("🔐 Starting Cybersecurity OSS Showcase Scraper...")
    
    # Initialize scraper
    scraper = GitHubScraper()
    
    if not scraper.github_token:
        print("⚠️ No GitHub token found. Rate limiting may occur.")
    
    # Load tools configuration
    print("📋 Loading tools configuration...")
    tools_config = load_tools_config()
    
    # Scrape data for all tools
    all_data = {}
    total_tools = sum(len(tools) for tools in tools_config.values())
    current_tool = 0
    
    for category, tools in tools_config.items():
        print(f"\n📂 Processing category: {category}")
        category_data = []
        
        for tool_config in tools:
            current_tool += 1
            repo_name = tool_config['repo']
            
            print(f"  [{current_tool}/{total_tools}] Fetching {repo_name}...")
            
            repo_data = scraper.get_repo_data(repo_name)
            
            if repo_data:
                # Merge config data with scraped data
                merged_data = {**tool_config, **repo_data}
                category_data.append(merged_data)
                print(f"    ✅ {repo_data['stars']} ⭐ | {scraper.format_time_ago(repo_data['last_commit_days_ago'])}")
            else:
                print(f"    ❌ Failed to fetch data")
            
            # Rate limiting
            time.sleep(0.5)
        
        all_data[category] = category_data
    
    # Save raw data
    print("\n💾 Saving data...")
    save_data(all_data, 'scraped_data.json')
    save_data({
        'last_updated': datetime.now().isoformat(),
        'total_tools': total_tools,
        'categories': len(all_data),
        'rate_limit_remaining': scraper.rate_limit_remaining
    }, 'metadata.json')
    
    # Generate README
    print("📝 Generating README...")
    readme_content = generate_readme(all_data)
    
    readme_path = Path(__file__).parent.parent / 'README.md'
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"\n🎉 Scraping completed!")
    print(f"   📊 Total tools processed: {total_tools}")
    print(f"   📂 Categories: {len(all_data)}")
    print(f"   ⏰ Rate limit remaining: {scraper.rate_limit_remaining}")
    print(f"   📝 README.md updated")

if __name__ == '__main__':
    main()