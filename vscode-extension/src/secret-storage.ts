import * as vscode from 'vscode';

export const SPECBOX_SECRET_KEY = 'specbox.mcpToken';

export class SecretsManager {
	constructor(private context: vscode.ExtensionContext) {}

	async getToken(): Promise<string | undefined> {
		return this.context.secrets.get(SPECBOX_SECRET_KEY);
	}

	async storeToken(token: string): Promise<void> {
		await this.context.secrets.store(SPECBOX_SECRET_KEY, token);
	}

	async deleteToken(): Promise<void> {
		await this.context.secrets.delete(SPECBOX_SECRET_KEY);
	}

	async hasToken(): Promise<boolean> {
		return (await this.getToken()) !== undefined;
	}
}
