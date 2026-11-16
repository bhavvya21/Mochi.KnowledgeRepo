CREATE TABLE `browser_sessions` (
	`token_hash` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`expires` integer NOT NULL
);
