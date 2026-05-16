import assert from 'node:assert/strict';
import test from 'node:test';

import worker from '../../worker-dashboard/src/index.js';
import { pageAccounts } from '../../worker-dashboard/src/pages/accounts.js';

const originalFetch = globalThis.fetch;

function installGitHubStub() {
	globalThis.fetch = async (url, init = {}) => {
		if (String(url).includes('api.github.com/repos/')) {
			return new Response(null, { status: 204 });
		}
		return originalFetch(url, init);
	};
}

function resetFetch() {
	globalThis.fetch = originalFetch;
}

test('worker rejects missing token', async () => {
	const response = await worker.fetch(new Request('https://example.com/api/trigger'), {});
	assert.equal(response.status, 401);
	assert.deepEqual(await response.json(), { success: false, error_code: 'AUTH_FAILED' });
});

test('worker reports dispatch failure without github token', async () => {
	const response = await worker.fetch(new Request('https://example.com/api/trigger?token=secret'), {
		WORKER_SECRET: 'secret',
	});
	assert.equal(response.status, 502);
	assert.deepEqual(await response.json(), { success: false, error_code: 'DISPATCH_FAILED' });
});

test('worker accepts matching token and defaults workflow', async () => {
	installGitHubStub();
	const response = await worker.fetch(new Request('https://example.com/api/trigger?token=secret'), {
		WORKER_SECRET: 'secret',
		GITHUB_REPO: 'ohwiki/msgflow',
		GITHUB_TOKEN: 'github-token',
	});
	resetFetch();
	assert.equal(response.status, 200);
	assert.deepEqual(await response.json(), {
		success: true,
		workflow: 'checkin',
		defaulted: true,
		dispatch_id: 'dispatch-placeholder',
	});
});

test('accounts page binds trigger targets explicitly', async () => {
	const response = await pageAccounts(new Request('https://example.com/'), {
		KV: {
			async list() {
				return { keys: [{ name: 'account:alice' }] };
			},
			async get() {
				return {
					username: 'alice',
					password: 'secret',
					platform: 'wucur',
					status: 'active',
				};
			},
		},
	});

	const html = await response.text();
	assert.match(html, /onclick="trigger\(event, 'alice'\)"/);
	assert.match(html, /onclick="trigger\(event, ''\)"/);
	assert.match(html, /function trigger\(event, target\)/);
});
