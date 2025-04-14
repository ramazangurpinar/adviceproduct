# Sprint Backlog

## Sprint 1

### Week 1 - User Registration & Authentication

| Epic | Role | User Story | Acceptance Criteria | Assigned to |
|------|------|------------|----------------------|-------------|
| User Registration & Authentication | As a new user | I want to register using my email address so that I can create an account and start using the platform immediately. | - Email field exists  <br> - Account created on valid data <br> - Session starts <br> - Redirects to confirmation page | Ramazan |
|  | As a user | I want to log in with my username and password so that I can securely access my account and continue where I left off. | - Form includes username and password <br> - Validates credentials <br> - Starts session <br> - Redirects to homepage <br> - Eye icon toggles password visibility <br> - JS handles toggle logic <br> - Applies to login and register forms <br> - Works across browsers | Mahek |
|  | As a user | I want to log in using my Google account so that I can skip filling out forms and access the platform quickly. | - User logs in using Google <br> - Auto-registers if new <br> - Session starts <br> - Redirects to homepage <br> - Email sent on first Google login | George |
|  | As a user who forgot their password | I want to reset it via email so that I can regain access to my account securely. | - User can request reset by entering email <br> - Email with reset link is sent <br> - Link includes secure token <br> - Reset link opens new password form <br> - New password must be confirmed <br> - Password updated securely <br> - User notified of success | Piero |

### Week 2 - User Profile & Settings

| Epic | Role | User Story | Acceptance Criteria | Assigned to |
|------|------|------------|----------------------|-------------|
| User Profile & Settings | As a user | I want to view my profile so that I can see my account information and verify that my personal details are accurate. | - Form includes username and password <br> - Validates credentials <br> - Starts session <br> - Redirects to homepage <br> - Shows error if invalid | Piero |
|  | As a user | I want to edit my profile information so that I can keep my personal details up to date. | - Form pre-filled with user data <br> - Fields: name, surname, email, country, age, gender <br> - Updates DB and session <br> - Redirects to profile | Mahek |
|  | As a user | I want to change my username by confirming my email and password so that I can update my identity securely. | - Form includes current email, password, new username <br> - Checks correctness <br> - Checks uniqueness <br> - Updates DB <br> - Sends confirmation email | Ramazan |
|  | As a user | I want to permanently delete my account so that I can remove all my data from the platform when I no longer wish to use it. | - Deletes user from DB <br> - Clears session <br> - Redirects to login <br> - Sends information email | George |

## Sprint 2

### Week 3 - Real-time Chat & AI Suggestions

| Epic | Role | User Story | Acceptance Criteria | Assigned to |
|------|------|------------|----------------------|-------------|
| Real-time Chat & AI Suggestions | As a user | I want to chat with the AI in real-time so that I can get instant responses without page reloads. | - Messages sent via WebSocket appear instantly <br> - Bot response is streamed without delay <br> - Page does not reload between turns | Ramazan |
|  | As a user | I want all my messages to be saved automatically so that I can view my past conversations whenever I need. | - User and bot messages are stored in DB <br> - Messages are linked to current conversation <br> - Messages can be retrieved later | George |
|  | As a user | I want to see product suggestions clearly during the chat so that I can quickly review and compare different options. | - Up to 3 suggestions shown at once <br> - Each suggestion has a name and description <br> - HTML formatting is visually clear | Mahek |
|  | As a user | I want to like or unlike product suggestions so that I can remember and revisit the ones I’m interested in. | - Like status persists across sessions <br> - Click toggles like/unlike immediately <br> - Update as liked in database | Piero |

### Week 4 - Conversation & History

| Epic | Role | User Story | Acceptance Criteria | Assigned to |
|------|------|------------|----------------------|-------------|
| Conversation & History | As a user | I want to start a fresh chat session so that I can get new product recommendations without mixing them with previous messages. | - A new conversation ID is generated <br> - Chat box is cleared when conversation starts | Mahek |
|  | As a user | I want to view my past conversations so that I can revisit previous suggestions and continue from where I left off. | - Past conversations are listed by title <br> - Each chat is clickable <br> - History loads with messages and suggestions | Ramazan |
|  | As a user | I want each conversation to have a meaningful AI-generated title so that I can easily recognize it in my chat history. | - Title is generated using AI and keywords <br> - Default title is replaced if relevant <br> - Titles are between 5-10 words | Piero |
|  | As a user | I want to end a conversation when I'm done so that the session is marked complete and doesn’t continue unnecessarily. | - Button ends current chat <br> - Bot sends 'conversation ended' message <br> - Conversation is marked inactive | George |

## Sprint 3

### Week 5 - Product & Favourites

| Epic | Role | User Story | Acceptance Criteria | Assigned to |
|------|------|------------|----------------------|-------------|
| Product & Favourites | As a user | I want to view detailed information about a recommended product so that I can learn more before making a decision. | - Product detail includes name, description, date <br> - Product links to original chat <br> - Page opens from favourites or chat | Ramazan |
|  | As a user | I want to see which message triggered a product suggestion so that I can understand the context of the recommendation. | - Product shows originating message <br> - Conversation title and date are shown <br> - Source chat is clickable | Piero |
|  | As a user | I want to browse a list of all the products I’ve liked so that I can revisit them later without searching. | - All liked products are grouped by conversation <br> - Each product shows sent time <br> - Liked list is accessible from navbar | George |
|  | As a user | I want to open a product in Google Shopping so that I can compare prices and availability easily. | - Button/link opens shopping URL <br> - Product name and category used in query <br> - Redirect opens in new tab | Mahek |

### Week 6 - AI Category Matching

| Epic | Role | User Story | Acceptance Criteria | Assigned to |
|------|------|------------|----------------------|-------------|
| AI Category Matching | As a user | I want the system to automatically detect the best category for each product so that the suggestions feel more relevant and organized. | - AI selects one category per level <br> - Path is stored if resolved fully <br> - Matched category ID saved in DB | Ramazan |
|  | As a user | I want to see the full category path of a product so that I can understand how it's classified in the system. | - Category path is readable (e.g. A > B > C) <br> - Shown on product detail page <br> - Full chain is resolved recursively | George |
|  | As a user | I want to manually choose or correct the category of a product so that I can help the system improve future suggestions. | - Select2 dropdown shows all categories <br> - Current selection is preselected <br> - Update button saves to DB | Mahek |
|  | As a user | I want to see how the AI decides each step of categorization so that I can trust and follow its decision-making process. | - Each level is shown as step <br> - Realtime AI selections are visualized <br> - Only 1 category per level is chosen | Piero |

## Sprint 4

### Week 7 - Logging Management

| Epic | Role | User Story | Acceptance Criteria | Assigned to |
|------|------|------------|----------------------|-------------|
| Logging Management | As an admin | I want to view logs of user activity so that I can monitor important actions and detect suspicious behavior. | - I can view logs of user actions such as login, logout, password changes, and profile updates <br> - Each log entry includes timestamp, user info, log type, and context <br> - I can filter logs by user, action type, or date range <br> - This helps me audit usage patterns and ensure system integrity | Ramazan |
|  | As an admin | I want to activate or deactivate specific log types so that I can control which events are being logged based on operational needs. | - I can access and update the log_types table directly <br> - Each log type has an isActive flag that determines whether it will be used in the system <br> - Inactive log types are automatically ignored during logging operations <br> - This allows me to reduce noise or disable irrelevant logs without changing application code | Piero |
|  | As a user | I want to review a history of my recent activity so that I can verify actions taken on my account. | - I can view a list of recent actions like login, logout, password changes <br> - Each action includes a date, time, and short description <br> - This gives me transparency and peace of mind about my account usage | Mahek |
| Session Management | As a user | I want my session to remain active when I refresh or revisit the page so that I don’t need to log in again unless I explicitly log out. | - My session is maintained for 30 minutes of inactivity <br> - If I close the browser and return within the session lifetime, I’m still recognized <br> - Session expires automatically only after timeout or logout | Ramazan |
|  | As an admin | I want each user's session start and end times to be logged so that I can monitor login durations and detect abnormal patterns. | - Session start is logged on login <br> - Session end is logged on logout or timeout <br> - These logs help in user activity auditing and security checks | Piero |
|  | As a user | I want to navigate between pages without losing my session so that I can use the system seamlessly without being logged out. | - I stay logged in while navigating the application <br> - If my session expires, I am redirected to the login page <br> - My identity is validated across routes via the session object | George |


### Week 8 - Email Communication

| Epic | Role | User Story | Acceptance Criteria | Assigned to |
|------|------|------------|----------------------|-------------|
| Email Communication | As an admin | I want to store email templates in the database so that they can be managed dynamically and updated without code changes. | - Templates must be saved with fields: name, subject, body. <br> - Each template must have a unique name used as an identifier. <br> - Templates can be fetched by name via query. <br> - Admins can later modify templates via backend or admin UI. | Piero |
|  | As an admin | I want to see logs of all outgoing emails so that I can ensure messages are being delivered successfully. | - Each log includes recipient, template name, status (sent/failed), and error (if any) <br> - I can search and filter logs by user or email type <br> - This helps identify delivery issues and improves system reliability | Ramazan |
|  | As a user | I want to view a history of emails sent to me by the system so that I can confirm important messages were delivered and take action if needed. | - I can see a list of emails sent to my account (e.g., password reset, username change) <br> - Each email entry includes the subject, date, time, and delivery status (sent/failed) <br> - I can use this list to verify that I received all important system communications | George |
|  | As a user | I want to send a support request through the Contact Us form so that I can get help from the support team when I face a problem. | - I can fill out a form with my message, subject, and contact details <br> - The system sends my request as an email to the support team <br> - I receive a confirmation that my request has been submitted successfully <br> - Optionally, I can be notified when my request is received or answered | Mahek |