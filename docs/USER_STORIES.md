# User Stories for Telegram Proxy Bot

## Overview
This document contains comprehensive user stories for all use cases supported by the SafeSurf Telegram Proxy Bot. Each story follows the standard format: "As a [user type], I want [goal] so that [benefit]."

## User Types
- **New User**: First-time bot user without subscription
- **Free Trial User**: User with active 1-day trial
- **Subscriber**: User with active paid subscription
- **Admin**: Bot administrator (configured in ADMIN_IDS)
- **Expired User**: User whose subscription has ended

---

## Epic 1: User Onboarding & Registration

### US-001: First Bot Interaction
**As a** new user  
**I want** to start the bot with `/start` command  
**So that** I can understand what the service offers and how to get started

**Acceptance Criteria:**
- Bot displays welcome message explaining proxy service
- Bot automatically creates my user account
- Bot shows current subscription status (none for new users)
- Bot offers subscription and free trial options
- My Telegram username and first name are saved

### US-002: Free Trial Access
**As a** new user  
**I want** to try the service for free  
**So that** I can evaluate the proxy quality before purchasing

**Acceptance Criteria:**
- I can click "Free Trial" button
- I receive 1-day free access immediately
- Bot confirms my trial period with expiration time
- I can access proxy configuration during trial
- I cannot get multiple free trials

---

## Epic 2: Subscription Management

### US-003: Subscription Purchase
**As a** new user or expired user  
**I want** to purchase a subscription  
**So that** I can access the proxy service

**Acceptance Criteria:**
- I can click "Subscribe" button
- Bot sends me a payment invoice via Telegram
- Invoice shows correct price and duration (30 days, $5.00)
- Payment is processed through YooKassa
- I receive confirmation after successful payment

### US-004: Subscription Renewal
**As a** subscriber with active subscription  
**I want** to extend my subscription  
**So that** I can continue using the service without interruption

**Acceptance Criteria:**
- I can purchase additional time while subscription is active
- New subscription time is added to existing expiration date
- Payment is processed successfully
- I receive confirmation with new expiration date

### US-005: Subscription Status Check
**As a** user  
**I want** to check my subscription status  
**So that** I know when my access expires

**Acceptance Criteria:**
- `/start` command shows my current subscription status
- I can see exact expiration date if subscribed
- Bot clearly indicates if subscription is expired
- Free trial users see trial expiration time

---

## Epic 3: Proxy Configuration Management

### US-006: Proxy Configuration Access
**As a** subscriber or trial user  
**I want** to get my proxy configuration  
**So that** I can set up Telegram to use the proxy

**Acceptance Criteria:**
- I can use `/config` command to see my proxy settings
- Configuration includes server address, port, and secret
- I receive direct tg:// links for easy setup
- Configuration works for all available proxy servers
- Bot prevents access if subscription is expired

### US-007: Proxy Configuration Generation
**As a** subscriber or trial user  
**I want** proxy configurations to be automatically created  
**So that** I don't need to manually request setup

**Acceptance Criteria:**
- Proxy configs are auto-generated when I first access `/config`
- Each proxy server gets a unique secret for my account
- Secrets are cryptographically secure (32 characters)
- Configuration persists across bot sessions

### US-008: Proxy Configuration Refresh
**As a** subscriber or trial user  
**I want** to refresh my proxy secrets  
**So that** I can improve security or resolve connection issues

**Acceptance Criteria:**
- I can click "Refresh Config" button
- All my proxy secrets are regenerated
- Old secrets become invalid immediately
- New configuration is displayed instantly
- Only works with active subscription

---

## Epic 4: Payment Processing

### US-009: Payment Pre-validation
**As a** user making a payment  
**I want** my payment to be validated before processing  
**So that** I don't encounter payment errors

**Acceptance Criteria:**
- Bot validates payment details before final processing
- Pre-checkout query is automatically approved for valid payments
- Payment flow continues smoothly to completion

### US-010: Payment Confirmation
**As a** user who completed payment  
**I want** to receive immediate confirmation  
**So that** I know my subscription is active

**Acceptance Criteria:**
- Payment is recorded in database with correct amount
- Subscription time is immediately activated/extended
- I receive confirmation message with expiration date
- Access to proxy configuration is immediately available

---

## Epic 5: Multi-Server Support

### US-011: Multiple Proxy Servers
**As a** subscriber  
**I want** access to multiple proxy servers  
**So that** I can choose the best performing server

**Acceptance Criteria:**
- I receive configuration for all available proxy servers
- Each server has unique credentials for my account
- All servers are displayed in single configuration message
- I can use any or all servers simultaneously

### US-012: Server Configuration Format
**As a** subscriber  
**I want** proxy configuration in standard format  
**So that** I can easily set up any Telegram client

**Acceptance Criteria:**
- Configuration includes server address and port
- MTProto secret is provided for each server
- Direct tg:// links are provided for convenience
- Configuration works with official Telegram clients

---

## Epic 6: Security & Access Control

### US-013: Subscription Validation
**As a** user  
**I want** my proxy access to be protected by subscription status  
**So that** only paying customers can use the service

**Acceptance Criteria:**
- All proxy-related commands check subscription status
- Expired users cannot access configuration
- Free trial users have full access during trial period
- Clear error messages when access is denied

### US-014: Secure Secret Generation
**As a** subscriber  
**I want** my proxy secrets to be cryptographically secure  
**So that** my connection is protected from unauthorized access

**Acceptance Criteria:**
- Secrets are 32 characters long
- Secrets use cryptographically secure random generation
- Each user gets unique secrets per server
- Secrets can be regenerated on demand

---

## Epic 7: User Experience & Navigation

### US-015: Inline Keyboard Navigation
**As a** user  
**I want** to navigate the bot using buttons  
**So that** I can easily access features without typing commands

**Acceptance Criteria:**
- Main menu shows relevant options based on subscription status
- Buttons work reliably and provide immediate feedback
- Navigation is intuitive and self-explanatory
- Callback queries are handled promptly

### US-016: Clear Status Messages
**As a** user  
**I want** to receive clear information about my account status  
**So that** I understand what actions are available to me

**Acceptance Criteria:**
- Welcome message explains service clearly
- Subscription status is always visible
- Error messages are helpful and actionable
- Success confirmations include relevant details

---

## Epic 8: Database & Data Management

### US-017: User Data Persistence
**As a** user  
**I want** my account information to be saved  
**So that** I don't lose my subscription or configuration

**Acceptance Criteria:**
- User account is created on first interaction
- Subscription status persists across sessions
- Proxy configurations are saved and retrievable
- Payment history is maintained

### US-018: Payment Records
**As a** user  
**I want** my payments to be properly recorded  
**So that** I have proof of purchase and subscription validity

**Acceptance Criteria:**
- All payments are logged with timestamp
- Payment amount and currency are recorded
- External payment provider ID is stored
- Payment status tracking (pending/completed)

---

## Future Enhancement Stories

### US-019: Admin Management
**As an** admin  
**I want** to manage users and view statistics  
**So that** I can monitor service usage and resolve issues

**Acceptance Criteria:**
- Admin commands for user management
- View subscription statistics
- Monitor payment activity
- Handle user support requests

### US-020: Usage Analytics
**As an** admin  
**I want** to track proxy usage statistics  
**So that** I can optimize server resources and pricing

**Acceptance Criteria:**
- Track connection counts per user
- Monitor bandwidth usage
- Server performance metrics
- User activity patterns

### US-021: Subscription Notifications
**As a** subscriber  
**I want** to receive warnings before my subscription expires  
**So that** I can renew without service interruption

**Acceptance Criteria:**
- 3-day expiration warning
- 1-day expiration warning
- Expiration notification
- Easy renewal options in notifications

### US-022: Refund Processing
**As a** user  
**I want** to request refunds for unsatisfactory service  
**So that** I can recover my payment if the service doesn't work

**Acceptance Criteria:**
- Refund request mechanism
- Admin approval process
- Automatic subscription adjustment
- Payment provider integration for refunds

---

## Technical User Stories

### TS-001: Configuration Management
**As a** system  
**I want** to parse environment variables correctly  
**So that** the bot can start with proper settings

**Acceptance Criteria:**
- Comma-separated values are parsed as lists
- All required configuration is validated on startup
- Clear error messages for missing configuration
- Support for different deployment environments

### TS-002: Database Schema Management
**As a** system  
**I want** to maintain proper database relationships  
**So that** data integrity is preserved

**Acceptance Criteria:**
- Foreign key constraints are enforced
- Database migrations handle schema changes
- Async database operations work reliably
- Connection pooling and error handling

### TS-003: Payment Provider Integration
**As a** system  
**I want** to integrate with YooKassa payment provider  
**So that** secure payment processing is available

**Acceptance Criteria:**
- Payment invoices are generated correctly
- Payment status updates are processed
- Error handling for payment failures
- Secure API communication with provider