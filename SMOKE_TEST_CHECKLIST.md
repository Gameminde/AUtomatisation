# Smoke Test Checklist

Run this on the target deployment after release.

## 1. Auth

- [ ] Open landing page
- [ ] Register with a valid activation code
- [ ] Log in successfully
- [ ] Log out successfully
- [ ] Log back in successfully

## 2. Settings And Profile

- [ ] Open Settings
- [ ] Save navigation language
- [ ] Reload and confirm the selected navigation language persists
- [ ] Save content language / tone / timezone
- [ ] Reload and confirm those settings persist

## 3. AI Provider Setup

- [ ] Open Settings -> AI provider section
- [ ] Select the intended provider
- [ ] Test a real API key
- [ ] Save the provider settings
- [ ] Reload and confirm provider/model persist

## 4. Facebook / Instagram

- [ ] Start Facebook OAuth from the app
- [ ] Complete the callback successfully
- [ ] Select a page in the page picker
- [ ] Confirm the connected page appears in Channels
- [ ] Confirm it appears in the Dashboard destination cards
- [ ] If Instagram is required, confirm the linked Instagram business account is detected

## 5. Dashboard

- [ ] Dashboard loads without section-level errors
- [ ] Setup banner reflects actual setup state
- [ ] Page card shows the connected page
- [ ] Health card shows Facebook token state
- [ ] If there are pending approvals, the cards show page/platform/language/source metadata

## 6. Studio

- [ ] Open Studio
- [ ] Confirm `Post`, `Carousel`, `Story sequence`, and `Reel script` are selectable in the active create flow
- [ ] Generate a `Post`
- [ ] Save draft
- [ ] Regenerate draft
- [ ] Approve/schedule draft
- [ ] Generate a `Carousel`
- [ ] Save draft
- [ ] Generate a `Story sequence`
- [ ] Save draft
- [ ] Generate a `Reel script`
- [ ] Save draft
- [ ] Confirm draft-only formats are not auto-published through the active flow

## 7. Approval Flow

- [ ] From Dashboard, approve a pending draft
- [ ] From Dashboard, reject a pending draft
- [ ] Confirm success/error toasts appear correctly
- [ ] Confirm the item leaves or updates in the approval queue

## 8. Publishing And Scheduling

- [ ] Confirm an approved post appears in scheduled content
- [ ] If publishing is enabled for the environment, publish one real post
- [ ] Confirm the published item appears in published content / dashboard metrics

## 9. Health View

- [ ] Open Health
- [ ] Confirm status, runtime, and events panels load
- [ ] Run at least one service test from the UI
- [ ] Confirm result messaging is visible and truthful

## 10. Telegram

- [ ] Open Settings -> Telegram
- [ ] Generate or display Telegram connect code
- [ ] Confirm Telegram connection status if worker is running
- [ ] Toggle daily summary on
- [ ] Reload and confirm it stays on
- [ ] Toggle daily summary off
- [ ] Reload and confirm it stays off

## 11. Disabled Surface Sanity Check

- [ ] `GET /api/insights` returns `410`
- [ ] `GET /api/status/modules` returns `410`
- [ ] `GET /api/randomization/config` returns `410`
- [ ] non-V1 A/B / virality endpoints return `410`

## 12. Security / Session Sanity

- [ ] Authenticated POST actions still work from the deployed web UI
- [ ] Cross-origin browser use is not required for the release environment
- [ ] If behind a proxy, original host/scheme are preserved so same-origin checks and OAuth still work
