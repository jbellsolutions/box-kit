# Running your own browser-box

Most people should not. If you are building an agent and need a browser, **call the shared box**
([calling.md](calling.md)). This page is for the operator of a box, and for the few cases where a
separate one is right.

## Why copies are the wrong default

The box runs no browser, so a copy is smaller than it used to be, but it still means its own
gateway, its own tokens and its own provider keys to keep current. Copies drift: a security fix
reaches the box that was redeployed and not the five that were cloned. And every copy spends from
its own browser budget, which the shared box's `status`, cost accounting and monthly caps know
nothing about.

The usual reasons for a copy, and what to do instead:

| "I need my own because..." | Instead |
|---|---|
| a call was refused at a limit | Browsers are hosted and run side by side up to the Browser Use plan's limit, so there is no lane to wait for. If it was the plan's limit or the box's monthly cap, retry later or ask the operator to raise it; use `fetch` where it answers. |
| I don't want to share a token | A token per caller is coming with the multi-browser gateway. Until then, ask the operator. |
| my project's compose file should have everything it needs | It needs `BROWSER_BOX_URL` and `BROWSER_BOX_TOKEN`, nothing else. Do not add `gateway` or `agent-*` services to another project. |
| I want it on my laptop for development | Fine, for developing browser-box itself. Stop it when you are done (`make down`), and do not point other projects at it. |

## When a separate box is right

- **A different owner.** Someone who is not the operator, with their own keys and their own bill.
  The public kit is [box-kit](https://github.com/jbellsolutions/box-kit).
- **A separate trust boundary.** Signed-in client accounts that must never share a machine with
  other work, decided by the operator, not by the project that wants it.
- **Developing browser-box.** A local stack for testing changes to this repo.

## Running one

The steps are in [operations.md](operations.md): host requirements, first deploy, `.env` (it needs
its own `BROWSER_USE_API_KEY`), updating code on a box with no GitHub credentials, and rotating the
token. Then register the box with its callers as in [calling.md](calling.md).
