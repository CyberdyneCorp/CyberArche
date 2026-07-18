# Tasks
- [ ] 1.1 Domain `PushSubscription`; `PushSubscriptionRepository` port; `PushSubscriptionUseCases` (subscribe/unsubscribe, caller-scoped)
- [ ] 1.2 In-memory + postgres repos; migration `0019_push_subscriptions.sql`
- [ ] 1.3 `WebPushNotificationChannel` (channel="push"): encrypt + deliver per subscription, prune expired; run pywebpush off the event loop
- [ ] 1.4 Router: `GET /push/vapid-public-key`, `POST`/`DELETE /push/subscriptions`
- [ ] 1.5 Config + wiring: VAPID settings; build the channel when configured; thread the subscription repo into channel building
- [ ] 1.6 Frontend: `static/sw.js`; `push.ts` (register/subscribe/unsubscribe, feature-guarded); wire to the push toggle with rollback on failure
- [ ] 1.7 Tests: channel delivery + expired-subscription pruning, subscription use case scoping, endpoints, push client guards; docs
- [ ] 1.8 `openspec validate web-push-channel --strict`; gates green
