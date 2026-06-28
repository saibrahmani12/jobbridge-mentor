"""JobBridge Mentor MCP Server — Career Tools via stdio transport.

Exposes 5 domain-specific tools:
  1. search_job_listings       — simulated job board search
  2. get_training_programs     — returns training programs for a skill/role
  3. analyze_resume_keywords   — ATS keyword gap analysis
  4. estimate_salary_range     — salary benchmarking by role and location
  5. find_career_resources     — local non-profit / support organisation finder
"""

from __future__ import annotations

import json
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("jobbridge-mentor-tools")

# ──────────────────────────────────────────────────────────────────────────────
# Tool 1: Job Listings Search
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def search_job_listings(
    role: str,
    location: str = "Remote",
    experience_level: str = "entry",
) -> str:
    """Search job listings for a given role, location, and experience level.

    Args:
        role: The job title or role to search for (e.g. 'data analyst', 'nurse').
        location: City, state, or 'Remote'. Defaults to Remote.
        experience_level: One of 'entry', 'mid', 'senior'. Defaults to 'entry'.

    Returns:
        JSON string containing a list of matching job listings.
    """
    # Simulated job database — in production this would call a real job board API
    listings_db = {
        "data analyst": [
            {"title": "Junior Data Analyst", "company": "TechCorp", "location": location,
             "salary": "$50,000–$65,000", "url": "https://jobs.example.com/1"},
            {"title": "Data Analyst I", "company": "City Health Dept", "location": location,
             "salary": "$48,000–$60,000", "url": "https://jobs.example.com/2"},
        ],
        "nurse": [
            {"title": "Registered Nurse", "company": "Community Hospital", "location": location,
             "salary": "$65,000–$80,000", "url": "https://jobs.example.com/3"},
            {"title": "LPN — Home Health", "company": "CarePlus Agency", "location": location,
             "salary": "$42,000–$55,000", "url": "https://jobs.example.com/4"},
        ],
        "software engineer": [
            {"title": "Junior Software Engineer", "company": "StartupXYZ", "location": location,
             "salary": "$70,000–$90,000", "url": "https://jobs.example.com/5"},
            {"title": "Software Engineer I", "company": "GovTech Solutions", "location": location,
             "salary": "$68,000–$85,000", "url": "https://jobs.example.com/6"},
        ],
        "customer service": [
            {"title": "Customer Support Specialist", "company": "RetailCo", "location": location,
             "salary": "$35,000–$45,000", "url": "https://jobs.example.com/7"},
            {"title": "Remote Customer Service Rep", "company": "TeleWork Inc", "location": "Remote",
             "salary": "$32,000–$42,000", "url": "https://jobs.example.com/8"},
        ],
    }

    role_lower = role.lower()
    matches = []
    for key, jobs in listings_db.items():
        if key in role_lower or role_lower in key:
            matches.extend(jobs)

    if not matches:
        matches = [
            {"title": f"{role.title()} — Entry Level", "company": "Various Employers",
             "location": location, "salary": "Competitive",
             "url": "https://www.indeed.com/q-" + role.replace(" ", "-") + "-jobs.html"},
        ]

    return json.dumps(
        {"role": role, "location": location, "experience_level": experience_level,
         "listings": matches[:5], "source": "JobBridge Job Board (simulated)"},
        indent=2,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Tool 2: Training Program Finder
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_training_programs(skill_or_role: str, budget: str = "free") -> str:
    """Find training programs and certifications for a given skill or target role.

    Args:
        skill_or_role: The skill or role to find training for (e.g. 'Python', 'project management').
        budget: 'free', 'low-cost' (under $500), or 'any'. Defaults to 'free'.

    Returns:
        JSON string with matching training programs.
    """
    programs = {
        "python": [
            {"name": "Python for Everybody", "provider": "Coursera / University of Michigan",
             "cost": "Free to audit", "duration": "8 months (2 hrs/week)", "url": "https://coursera.org/specializations/python"},
            {"name": "CS50P: Python", "provider": "Harvard / edX",
             "cost": "Free to audit", "duration": "Self-paced", "url": "https://cs50.harvard.edu/python"},
        ],
        "project management": [
            {"name": "Google Project Management Certificate", "provider": "Coursera / Google",
             "cost": "~$49/month (financial aid available)", "duration": "6 months (10 hrs/week)",
             "url": "https://coursera.org/professional-certificates/google-project-management"},
            {"name": "Intro to Project Management", "provider": "edX / Alison",
             "cost": "Free", "duration": "4–6 hours", "url": "https://alison.com/courses/project-management"},
        ],
        "data": [
            {"name": "Google Data Analytics Certificate", "provider": "Coursera / Google",
             "cost": "~$49/month (financial aid available)", "duration": "6 months",
             "url": "https://coursera.org/professional-certificates/google-data-analytics"},
            {"name": "Data Literacy Fundamentals", "provider": "DataCamp",
             "cost": "Free (first chapter)", "duration": "4 hours", "url": "https://datacamp.com"},
        ],
        "healthcare": [
            {"name": "Community Health Worker Training", "provider": "Local Community Colleges",
             "cost": "Subsidised / Pell Grant eligible", "duration": "3–6 months", "url": "https://www.nachw.org"},
            {"name": "CPR & First Aid Certification", "provider": "Red Cross",
             "cost": "$20–$75", "duration": "1 day", "url": "https://redcross.org/training"},
        ],
        "default": [
            {"name": "LinkedIn Learning (free via library)", "provider": "LinkedIn / Public Libraries",
             "cost": "Free with library card", "duration": "Self-paced", "url": "https://www.linkedin.com/learning"},
            {"name": "Coursera Financial Aid", "provider": "Coursera",
             "cost": "Free (apply for aid)", "duration": "Varies", "url": "https://coursera.org"},
            {"name": "Alison Free Courses", "provider": "Alison",
             "cost": "Free", "duration": "Varies", "url": "https://alison.com"},
        ],
    }

    key = skill_or_role.lower()
    matched = []
    for db_key, items in programs.items():
        if db_key in key or key in db_key:
            matched.extend(items)

    if not matched:
        matched = programs["default"]

    return json.dumps(
        {"skill_or_role": skill_or_role, "budget": budget, "programs": matched},
        indent=2,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Tool 3: Resume ATS Keyword Analyzer
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def analyze_resume_keywords(resume_text: str, target_role: str) -> str:
    """Analyze a resume for ATS keyword gaps relative to a target role.

    Args:
        resume_text: The resume content as plain text.
        target_role: The role being applied for.

    Returns:
        JSON string with present keywords, missing keywords, and an ATS score estimate.
    """
    role_keywords = {
        "data analyst": ["sql", "python", "excel", "tableau", "power bi", "data visualization",
                         "statistical analysis", "reporting", "dashboard", "data cleaning"],
        "software engineer": ["python", "java", "javascript", "git", "api", "rest", "agile",
                              "unit testing", "cloud", "ci/cd"],
        "project manager": ["pmp", "agile", "scrum", "stakeholder", "budget", "timeline",
                            "risk management", "deliverables", "kpi", "cross-functional"],
        "nurse": ["patient care", "ehr", "clinical", "medication administration", "assessment",
                  "hipaa", "triage", "documentation", "care plan", "bls"],
        "customer service": ["communication", "problem solving", "crm", "conflict resolution",
                             "multi-tasking", "empathy", "sales", "ticketing system", "kpi"],
    }

    role_key = target_role.lower()
    keywords = role_keywords.get(role_key, [])
    if not keywords:
        for key in role_keywords:
            if key in role_key or role_key in key:
                keywords = role_keywords[key]
                break

    if not keywords:
        keywords = ["communication", "teamwork", "problem solving", "leadership",
                    "microsoft office", "time management"]

    resume_lower = resume_text.lower()
    present = [kw for kw in keywords if kw in resume_lower]
    missing = [kw for kw in keywords if kw not in resume_lower]
    score = int((len(present) / max(len(keywords), 1)) * 100)

    recommendations = []
    if score < 50:
        recommendations.append("Add more role-specific keywords to improve ATS ranking significantly.")
    if missing:
        recommendations.append(f"Consider adding: {', '.join(missing[:5])} to your resume.")
    recommendations.append("Quantify achievements with numbers/percentages wherever possible.")

    return json.dumps(
        {"target_role": target_role, "ats_score_estimate": f"{score}%",
         "keywords_present": present, "keywords_missing": missing,
         "recommendations": recommendations},
        indent=2,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Tool 4: Salary Range Estimator
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def estimate_salary_range(role: str, location: str = "United States", experience_years: int = 0) -> str:
    """Estimate the salary range for a given role, location, and experience level.

    Args:
        role: Job title to look up.
        location: City/state or country. Defaults to 'United States'.
        experience_years: Years of experience (0 = entry level). Defaults to 0.

    Returns:
        JSON string with salary range and market context.
    """
    base_salaries = {
        "data analyst": (48000, 65000),
        "software engineer": (70000, 95000),
        "project manager": (60000, 85000),
        "nurse": (55000, 80000),
        "customer service": (32000, 48000),
        "teacher": (42000, 65000),
        "accountant": (52000, 75000),
        "marketing coordinator": (40000, 58000),
        "warehouse associate": (30000, 45000),
    }

    role_lower = role.lower()
    low, high = 35000, 55000  # default
    for key, (l, h) in base_salaries.items():
        if key in role_lower or role_lower in key:
            low, high = l, h
            break

    # Experience multiplier
    exp_bump = min(experience_years * 0.04, 0.40)
    low_adj = int(low * (1 + exp_bump))
    high_adj = int(high * (1 + exp_bump))

    # Location adjustment (simplified)
    location_lower = location.lower()
    location_multiplier = 1.0
    if any(city in location_lower for city in ["san francisco", "new york", "seattle", "boston"]):
        location_multiplier = 1.35
    elif any(city in location_lower for city in ["chicago", "los angeles", "austin", "denver"]):
        location_multiplier = 1.15
    elif "remote" in location_lower:
        location_multiplier = 1.05

    low_final = int(low_adj * location_multiplier)
    high_final = int(high_adj * location_multiplier)

    return json.dumps(
        {
            "role": role,
            "location": location,
            "experience_years": experience_years,
            "estimated_salary_range": f"${low_final:,} – ${high_final:,} / year",
            "median_estimate": f"${int((low_final + high_final) / 2):,} / year",
            "data_source": "BLS & Glassdoor aggregated benchmarks (simulated)",
            "tip": "Negotiate for the upper end if you have relevant certifications or transferable skills.",
        },
        indent=2,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Tool 5: Career Support Resources
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def find_career_resources(barrier: str = "general", location: str = "United States") -> str:
    """Find non-profit organisations, government programs, and career centres.

    Args:
        barrier: The barrier the job seeker faces, e.g. 'disability', 'criminal record',
                 'veteran', 'single parent', 'immigrant', 'youth', 'general'.
        location: City/state or 'general' for national resources.

    Returns:
        JSON string with relevant support organisations and programs.
    """
    resources = {
        "disability": [
            {"name": "National Organization on Disability", "url": "https://nod.org",
             "services": "Employment programs for people with disabilities"},
            {"name": "Ticket to Work (SSA)", "url": "https://choosework.ssa.gov",
             "services": "Free job support for people receiving SSA benefits"},
        ],
        "criminal record": [
            {"name": "70 Million Jobs", "url": "https://www.70millionjobs.com",
             "services": "Job platform specifically for people with records"},
            {"name": "Ban the Box / Fair Chance Employers", "url": "https://bantheboxcampaign.org",
             "services": "Lists employers committed to fair-chance hiring"},
        ],
        "veteran": [
            {"name": "American Job Centers — Veterans", "url": "https://www.careeronestop.org/Veterans",
             "services": "Career counselling, training, and job placement for veterans"},
            {"name": "Hire Heroes USA", "url": "https://www.hireheroesusa.org",
             "services": "Free transition assistance for US veterans and spouses"},
        ],
        "single parent": [
            {"name": "National Caucus and Center on Black Aging", "url": "https://www.ncba-aging.org",
             "services": "Workforce programs for underrepresented groups including single parents"},
            {"name": "Child Care Aware", "url": "https://www.childcareaware.org",
             "services": "Find affordable childcare to enable return to work"},
        ],
        "immigrant": [
            {"name": "Upwardly Global", "url": "https://www.upwardlyglobal.org",
             "services": "Career programs for immigrants and refugees"},
            {"name": "IMLS Workforce Development", "url": "https://www.imls.gov",
             "services": "Library-based workforce programs available nationwide"},
        ],
        "youth": [
            {"name": "YouthBuild USA", "url": "https://youthbuild.org",
             "services": "Education and job training for young adults (16–24)"},
            {"name": "Job Corps", "url": "https://www.jobcorps.gov",
             "services": "Free education and vocational training for youth"},
        ],
        "general": [
            {"name": "American Job Centers", "url": "https://www.careeronestop.org/LocalHelp/find-american-job-centers.aspx",
             "services": "Free career counselling, resume help, and job placement nationwide"},
            {"name": "Goodwill Industries", "url": "https://www.goodwill.org/jobs-training",
             "services": "Free job training and placement programs"},
            {"name": "United Way 211", "url": "https://www.211.org",
             "services": "Connects to local social services including job programs"},
        ],
    }

    barrier_lower = barrier.lower()
    matched = resources.get(barrier_lower, resources["general"])

    # Always append general resources
    if barrier_lower != "general":
        matched = matched + resources["general"][:2]

    return json.dumps(
        {"barrier": barrier, "location": location, "resources": matched,
         "note": "All listed resources offer free or subsidised services."},
        indent=2,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
