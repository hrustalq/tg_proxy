# YooKassa Payment Provider Setup Guide

This guide explains how to set up YooKassa as a payment provider for your Telegram proxy bot.

## Prerequisites

- Telegram bot created via @BotFather
- YooKassa merchant account
- Russian business registration (YooKassa primarily serves Russian market)

## Step 1: Create YooKassa Account

1. **Visit YooKassa Website**
   - Go to https://yookassa.ru
   - Click "Подключиться" (Connect) button

2. **Business Registration**
   - Provide business details (required for Russian entities)
   - Submit required documents
   - Wait for account approval

3. **Get API Credentials**
   - Login to YooKassa dashboard
   - Navigate to "API" section
   - Copy your Shop ID and Secret Key
   - Format: `shop_id:secret_key`

## Step 2: Connect YooKassa to Telegram Bot

1. **Open BotFather**
   - Start chat with @BotFather on Telegram
   - Use `/mybots` command

2. **Configure Payments**
   - Select your bot
   - Go to "Bot Settings" → "Payments"
   - Choose "YooKassa" from the provider list

3. **Enter YooKassa Details**
   - Shop ID: Your YooKassa shop identifier
   - Secret Key: Your YooKassa secret key
   - Test Mode: Enable for testing

4. **Get Provider Token**
   - BotFather will provide a provider token
   - Save this token securely
   - Format: `381764678:TEST:your_token_here`

## Step 3: YooKassa Dashboard Configuration

1. **Payment Methods**
   - Enable desired payment methods (cards, wallets, etc.)
   - Configure currencies (RUB is primary)
   - Set payment limits

2. **Webhook Settings**
   - Configure webhook URL for payment notifications
   - Set up callback URLs for success/failure

3. **Test Environment**
   - Use test credentials for development
   - Test Shop ID: `54401`
   - Test Secret Key: `test_your_secret_key`

## Step 4: Testing

### Test Payment Details

**Test Cards:**
- Successful payment: `4111 1111 1111 1111`
- Failed payment: `4000 0000 0000 0002`
- CVV: Any 3 digits
- Expiry: Any future date

**Test Wallets:**
- YooMoney: Use test account
- Qiwi: Use test phone number

### Test Process

1. **Enable Test Mode**
   - In BotFather: Bot Settings → Payments → Test Mode
   - Use test provider token

2. **Test Payment Flow**
   - Send test invoice via bot
   - Complete payment with test card
   - Verify webhook notifications

## Step 5: Go Live

1. **Production Readiness**
   - Complete YooKassa account verification
   - Provide all required business documents
   - Set up customer support channels

2. **Switch to Live Mode**
   - In BotFather: Bot Settings → Payments → Live Mode
   - Get live provider token
   - Update bot configuration

3. **Final Checklist**
   - ✅ Account fully verified
   - ✅ Payment methods configured
   - ✅ Webhook endpoints tested
   - ✅ Customer support ready
   - ✅ Terms of service published

## Environment Variables

Update your `.env` file:

```env
# YooKassa Configuration
PAYMENT_PROVIDER_TOKEN=381764678:TEST:your_yookassa_token_here
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key
```

## Common Issues

### Issue 1: Provider Not Available
- **Cause**: YooKassa may not be available in your region
- **Solution**: Use alternative providers like Stripe, Sberbank

### Issue 2: Account Verification
- **Cause**: Missing business documents
- **Solution**: Complete all required documentation

### Issue 3: Payment Failures
- **Cause**: Incorrect API credentials
- **Solution**: Verify Shop ID and Secret Key

### Issue 4: Test Mode Issues
- **Cause**: Using live credentials in test mode
- **Solution**: Use proper test credentials

## Alternative Providers

If YooKassa is not available:

1. **Stripe** (Global)
   - Test token: `284685063:TEST:...`
   - Supports most countries

2. **Sberbank** (Russia)
   - Good alternative for Russian market
   - Similar setup process

3. **Razorpay** (India)
   - For Indian market
   - Supports INR currency

## Support

- **YooKassa Support**: support@yookassa.ru
- **Telegram Bot Support**: @BotSupport
- **Documentation**: https://yookassa.ru/developers/

## Security Notes

- ⚠️ Never share secret keys publicly
- ⚠️ Use HTTPS for webhook endpoints
- ⚠️ Validate all webhook signatures
- ⚠️ Store credentials securely

## Next Steps

After setup is complete:
1. Update your bot code with the provider token
2. Test the complete payment flow
3. Monitor payments in YooKassa dashboard
4. Set up automated receipt generation (if required)