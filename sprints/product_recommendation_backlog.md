# AI Product Recommendation System — Backlog Plan

This document outlines the EPICs, User Stories, and detailed Acceptance Criteria for a 4-sprint agile development plan.

---

## ✅ EPIC 1: User Registration & Authentication

### User Story 1.1 — Register with Email/Password
**As a user**, I want to register with email and password so that I can access the system securely.

**Acceptance Criteria**
- Required fields must not be empty
- Email must be unique in the system
- Password must be securely hashed using bcrypt
- User is redirected to success page after registration

### User Story 1.2 — Login with Credentials
**As a user**, I want to log in securely using my credentials.

**Acceptance Criteria**
- Incorrect credentials result in error message
- Correct credentials create a valid session
- User is redirected to homepage after login

### User Story 1.3 — Google Login
**As a user**, I want to log in with Google so I can access the system easily.

**Acceptance Criteria**
- Existing users are matched via email
- New users are created only once
- User session is established with Google info

### User Story 1.4 — Password Reset via Email
**As a user**, I want to reset my password via email if I forget it.

**Acceptance Criteria**
- Reset link expires in 1 hour
- Expired or invalid tokens are gracefully handled
- Password must be changed only after token verification

---

## ✅ EPIC 2: User Profile & Settings

### User Story 2.1 — View Profile
**As a user**, I want to view my profile so I can see my information.

**Acceptance Criteria**
- Profile includes name, email, username
- Optional fields are shown if provided
- Only logged-in users can view profile

### User Story 2.2 — Edit Profile
**As a user**, I want to update my personal details.

**Acceptance Criteria**
- Fields are pre-filled with current data
- Changes are saved to the database
- Confirmation is shown after update

### User Story 2.3 — Change Username
**As a user**, I want to change my username securely.

**Acceptance Criteria**
- User must confirm with password
- New username must be unique
- A confirmation email is sent after change

### User Story 2.4 — Delete Account
**As a user**, I want to delete my account permanently.

**Acceptance Criteria**
- System asks for confirmation
- User and associated data are removed
- Confirmation email is sent to user

---

## ✅ EPIC 3: Real-time Chat & AI Suggestions

### User Story 3.1 — Real-time Chat
**As a user**, I want to chat with AI in real-time.

**Acceptance Criteria**
- Messages sent via WebSocket appear instantly
- Bot response is streamed without delay
- Page does not reload between turns

### User Story 3.2 — Save Messages
**As a user**, I want my messages to be saved.

**Acceptance Criteria**
- User and bot messages are stored in DB
- Messages are linked to current conversation
- Messages can be retrieved later

### User Story 3.3 — Show Product Suggestions
**As a user**, I want to see product cards in chat.

**Acceptance Criteria**
- Up to 3 suggestions shown at once
- Each suggestion has a name and description
- HTML formatting is visually clear

### User Story 3.4 — Like Product Suggestions
**As a user**, I want to like/unlike product suggestions.

**Acceptance Criteria**
- Like status persists across sessions
- Click toggles like/unlike immediately
- Changes reflect in database

---

## ✅ EPIC 4: Conversation & History

### User Story 4.1 — Start New Chat
**As a user**, I want to start a new session.

**Acceptance Criteria**
- A new conversation ID is generated
- Session is created in DB
- Chat box is cleared when session starts

### User Story 4.2 — View Past Sessions
**As a user**, I want to review old chats.

**Acceptance Criteria**
- Past conversations are listed by title
- Each chat is clickable
- History loads with messages and suggestions

### User Story 4.3 — AI-Generated Titles
**As a user**, I want meaningful chat titles.

**Acceptance Criteria**
- Title is generated using AI and keywords
- Default title is replaced if relevant
- Titles are between 5-10 words

### User Story 4.4 — End Conversation
**As a user**, I want to end chat manually.

**Acceptance Criteria**
- Button ends current chat
- Bot sends "conversation ended" message
- Session is marked inactive

---

## ✅ EPIC 5: Product & Favourites

### User Story 5.1 — View Product Detail
**As a user**, I want to explore each product in detail.

**Acceptance Criteria**
- Product detail includes name, description, date
- Product links to original chat
- Page opens from favourites or chat

### User Story 5.2 — View Conversation Source
**As a user**, I want to know where the suggestion came from.

**Acceptance Criteria**
- Product shows originating message
- Conversation title and date are shown
- Source chat is clickable

### User Story 5.3 — View Liked Products
**As a user**, I want to browse my favourites.

**Acceptance Criteria**
- All liked products are grouped by session
- Each product shows sent time
- Liked list is accessible from navbar

### User Story 5.4 — Open in Google Shopping
**As a user**, I want to compare products in Google.

**Acceptance Criteria**
- Button/link opens shopping URL
- Product name and category used in query
- Redirect opens in new tab

---

## ✅ EPIC 6: AI Category Matching

### User Story 6.1 — Auto Category Matching
**As a user**, I want AI to assign product categories.

**Acceptance Criteria**
- AI selects one category per level
- Path is stored if resolved fully
- Matched category ID saved in DB

### User Story 6.2 — View Category Path
**As a user**, I want to see product hierarchy.

**Acceptance Criteria**
- Category path is readable (e.g. A > B > C)
- Shown on product detail page
- Full chain is resolved recursively

### User Story 6.3 — Manual Category Assignment
**As a user**, I want to pick a category manually.

**Acceptance Criteria**
- Select2 dropdown shows all categories
- Current selection is preselected
- Update button saves to DB

### User Story 6.4 — Step-by-Step AI Logic
**As a user**, I want to understand category suggestions.

**Acceptance Criteria**
- Each level is shown as step
- Realtime AI selections are visualized
- Only 1 category per level is chosen

---

## ✅ EPIC 7: Admin & Logging

### User Story 7.1 — Log User Actions
**As an admin**, I want to monitor activity.

**Acceptance Criteria**
- Login, logout, register, edit actions logged
- Logs are stored in `app_logs`
- Timestamp and user ID are saved

### User Story 7.2 — Log Sent Emails
**As an admin**, I want to track emails.

**Acceptance Criteria**
- Email logs include subject, status, error
- Template name is logged
- Recipient address is stored

### User Story 7.3 — Log Type Classification
**As an admin**, I want to filter log types.

**Acceptance Criteria**
- All logs include log_type_id
- Log types are listed in a table
- Types include AI, USER, SYSTEM categories

### User Story 7.4 — Log AI Failures
**As an admin**, I want to trace AI issues.

**Acceptance Criteria**
- AskDeepSeek exceptions are caught
- Logs include conversation and error
- Failures are visible in log table

---

## ✅ EPIC 8: Email Communication

### User Story 8.1 — Contact Form Email
**As a user**, I want to send support requests.

**Acceptance Criteria**
- Contact form includes name, email, message
- Sends email to admin inbox
- Success page is shown after send

### User Story 8.2 — Welcome Email
**As a user**, I want to feel welcomed.

**Acceptance Criteria**
- Welcome email is sent after signup
- Includes personalized message
- Template from DB is used

### User Story 8.3 — Password Change Email
**As a user**, I want confirmation after changing password.

**Acceptance Criteria**
- Email sent after reset/change
- Token link expires in 1 hour
- Includes security message

### User Story 8.4 — Email Template System
**As a user**, I want pretty emails.

**Acceptance Criteria**
- Templates stored in database
- Rendered with Jinja2 engine
- Emails match brand formatting