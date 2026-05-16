import assert from 'node:assert/strict';
import test from 'node:test';

import { pageAccounts } from '../../worker-dashboard/src/pages/accounts.js';

test('worker admin ui renders account list and trigger controls', async () => {
	const response = await pageAccounts(new Request('https://example.com/'), {
		KV: {
			async list() {
				return { keys: [{ name: 'account:alice' }, { name: 'account:bob' }] };
			},
			async get(name) {
				if (String(name).includes('alice')) {
					return {
						username: 'alice',
						password: 'secret',
						platform: 'wucur',
						status: 'active',
						checkin_time: '2026-05-16T08:00:00Z',
					};
				}
				return {
					username: 'bob',
					password: 'secret',
					platform: 'wucur',
					status: 'pending',
				};
			},
		},
	});

	const html = await response.text();
	assert.match(html, /账号管理/);
	assert.match(html, /今日签到/);
	assert.match(html, /onclick="trigger\(event, 'alice'\)"/);
	assert.match(html, /onclick="trigger\(event, 'bob'\)"/);
	assert.match(html, /onclick="showDetail\('alice'\)"/);
	assert.match(html, /账号详情/);
	assert.match(html, /最近结果/);
	assert.match(html, /🔄 手动触发签到/);
	assert.match(html, /function trigger\(event, target\)/);
});
