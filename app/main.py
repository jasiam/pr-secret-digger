import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

import requests
from unidiff import PatchSet

API_BASE_URL = "https://api.github.com/repos"
TEMP_DIR = "/tmp/pr_digger"
SEPARATOR = "#_#"
PR_FILENAME = "prs.json"
PR_CHECKED_FILENAME = "prs_checked.json"
TOTAL_REMAINING_REQUESTS = 0
DIFF_REQUESTS_PRINT_LIMIT = 100


def get_all_pull_requests(url, project_path):
    global TOTAL_REMAINING_REQUESTS
    if (
        os.path.isfile(f"{project_path}/{PR_FILENAME}")
        and os.path.getsize(f"{project_path}/{PR_FILENAME}") > 0
    ):  # Retrieve pull requests from file
        with open(f"{project_path}/{PR_FILENAME}", "r", encoding='utf-8') as pr_file:
            prs_json = pr_file.read()
            return json.loads(prs_json)
    params = {"per_page": 100, "state": "closed"}

    # RETRIEVE ALL PULL REQUESTS WITH PAGINATION
    pull_requests = []
    is_next = True
    with open(f"{project_path}/{PR_FILENAME}", "w", encoding='utf-8') as pr_file:
        while is_next:
            is_next = False
            response = requests.get(
                url, headers=headers, params=params, timeout=30)
            if response.status_code == 200:
                pull_requests += json.loads(response.text)
                print(f"{len(pull_requests)} pull requests retrieved")
                if response.headers.get("Link"):
                    for elem in response.headers["Link"].split(", "):
                        if re.match('.*; rel="next"$', elem):
                            url = elem.split("; ")[0][1:-1]
                            is_next = True
                            break
                    TOTAL_REMAINING_REQUESTS = response.headers["X-RateLimit-Remaining"]
            else:
                print(
                    f"Failed to retrieve pull requests. Status code: {response.status_code}. Reason: {response.reason}")
                sys.exit(0)
        print(
            "All pull requests have been retrieved. This step will be step in the future unless you delete the temporary folder created for this project"
        )
        pr_file.write(json.dumps(pull_requests))
    return pull_requests


def custom_check_secrets_in_diff(diff_text, pr):
    global found_secrets
    patch_set = PatchSet.from_string(diff_text)
    with open(os.path.join(os.path.dirname(__file__), "regexes.json"), "r", encoding='utf-8') as f:
        regexes = json.loads(f.read())

    for key in regexes:
        regexes[key] = re.compile(regexes[key])

    for patch_file in patch_set:
        filename = patch_file.path

        code_lines = (
            filename,
            [
                (line.target_line_no, line.value)
                for chunk in patch_file
                # target_lines refers to incoming (new) changes
                for line in chunk.target_lines()
                if line.is_added
            ],
        )

        for line in code_lines[1]:
            for secret_type, compiled_pattern in regexes.items():
                if line[1].strip() not in found_secrets:
                    found = compiled_pattern.findall(line[1].strip())
                    if found:
                        found_secrets.append(line[1].strip())
                        print("\nSECRET FOUND:")
                        print(
                            f"Pull Request #{pr['number']} created at {pr['created_at']} Title: {pr['title']} - Created by: {pr['user']['login']}"
                        )
                        print(f"{secret_type} found\nFile: {code_lines[0]}")
                        print(f"Secret:{line[1].strip()}\n")


def retrieve_pr_diff(pr_url):
    global TOTAL_REMAINING_REQUESTS
    diff_response = requests.get(pr_url, headers=diff_headers, timeout=30)
    if diff_response.status_code == 200:
        remaining_requests = diff_response.headers["X-RateLimit-Remaining"]
        # Init total_remaining_requests in case PRs were already retrieved in a previous execution
        if TOTAL_REMAINING_REQUESTS == 0:
            TOTAL_REMAINING_REQUESTS = remaining_requests

        if (
            int(TOTAL_REMAINING_REQUESTS) - int(remaining_requests)
            == DIFF_REQUESTS_PRINT_LIMIT
        ):
            print(f"Rate Limit left: {remaining_requests}")
            TOTAL_REMAINING_REQUESTS = remaining_requests

    elif (
        diff_response.status_code == 403
        and diff_response.reason == "rate limit exceeded"
    ):
        now = datetime.now()
        resume_time = now + timedelta(hours=1, seconds=10)
        print(
            f"Rate limit exceeded, scan will continue at {resume_time} automatically (or you can execute it later on your own, it will resume from this point)"
        )
        time.sleep(3610)
        retrieve_pr_diff(pr_url)
    else:
        print(
            f"Failed to retrieve pull request #{pr['number']} diff content. Status code: {diff_response.status_code}. Reason: {diff_response.reason}"
        )
    return diff_response


if __name__ == "__main__":
    URL = sys.argv[1]
    headers = {}
    if os.getenv('ACCESS_TOKEN'):
        headers = {"Authorization": f"token {os.getenv('ACCESS_TOKEN')}"}
    found_secrets = []
    user_repo = re.search(
        r"https:\/\/github\.com\/([\w\-\.]+)\/([\w\-\.]+)", URL)
    target_url = f"{API_BASE_URL}/{user_repo.groups()[0]}/{user_repo.groups()[1]}/pulls"
    project_path = os.path.normpath(
        f"{TEMP_DIR}/{user_repo.groups()[0]}{SEPARATOR}{user_repo.groups()[1]}"
    )
    os.makedirs(project_path, exist_ok=True)
    all_pull_requests = get_all_pull_requests(target_url, project_path)
    diff_headers = headers
    diff_headers["Accept"] = "application/vnd.github.diff"
    checked_prs = {}

    if os.path.isfile(f"{project_path}/{PR_CHECKED_FILENAME}"):
        f = open(f"{project_path}/{PR_CHECKED_FILENAME}", encoding="utf-8")
        checked_prs = f.read().splitlines()
        f.close()

    with open(f"{project_path}/{PR_CHECKED_FILENAME}", "a", encoding="utf-8") as checked_file:
        for pr in [
            pull_request
            for pull_request in all_pull_requests
            if str(pull_request["number"]) not in checked_prs
        ]:
            pr_url = f"{target_url}/{pr['number']}"
            diff_file_response = retrieve_pr_diff(pr_url)
            if diff_file_response.status_code == 200:
                custom_check_secrets_in_diff(diff_file_response.text, pr)
                checked_file.write(f"{pr['number']}\n")
            elif diff_file_response.status_code == 404:
                continue
            else:
                sys.exit(0)
    print(f"Scan finished at {datetime.now()}")
