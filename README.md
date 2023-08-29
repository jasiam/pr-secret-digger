# PR-SECRET-DIGGER

Pr-secret-digger is a tool to find secrets in github repositories by digging into every pull request which has ever been opened by using the Github API.

The idea came up after opening a pull request containing a telegram bot token by accident, I thought it would be trivial to delete a PR from a repo I own, but after several attempts I finally checked that the only possible way to remove that pull request was contacting directly with Github support asking for its deletion. Even if you close the PR and delete the source branch, the PR and its content will still be available through Github API or UI.

## Usage

Clone this repository and go into pr-secret-digger directory

Build docker image

```shell script
docker build -t pr-secret-digger .
```

Run docker image and execute script

```shell script
docker run -ti --name pr-secret-digger -e ACCESS_TOKEN=XXXXXXXX pr-secret-digger
root@15dd60f6653c:/app# python main.py https://github.com/jasiam/test-secrets-in-pr
```
>**Note**
>
> https://github.com/jasiam/test-secrets-in-pr is a test repository for this tool


### Rate limits

Github API Rate Limit is different depending on the identity associated with the request, you can check all the scenarios [here](https://docs.github.com/en/rest/overview/resources-in-the-rest-api?apiVersion=2022-11-28#rate-limiting)

The basics:
- No Authentication: 60 requests/hour (without ACCESS_TOKEN)
- Using a Github personal access token: 5000 requests/hour

>**Note**
>
> You don't need to grant any kind of permission to your personal access token to scan public repositories

In case you reach the Github API Rate limit during an execution, the tool will pause and wait until it's allowed to make requests again. Of course you can always stop the execution, change your source ip address (using a proxy or a VPN provider) and execute it again since Github applies the rate limit for the origin IP address, the tool will resume from the last checked PR from previous execution.

### Secrets detection engine

Secrets are detected thanks to [truffleHog](https://github.com/trufflesecurity/trufflehog) regexes, which are publicly available [here](https://github.com/dxa4481/truffleHogRegexes)