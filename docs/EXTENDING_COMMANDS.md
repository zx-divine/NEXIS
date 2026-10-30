# Extending commands

1. Define the typed action's description, argument requirements, risk and permission
   in core/commands.py. Default new/unrecognised actions to rejection.
2. Add strict argument and resource validation to Engine.prepare. Return a Preview
   that truthfully names the target and effect. Do not perform the action in validation.
3. Add the handler in Engine.dispatch, using an explicit platform/service interface.
   Return Result only after the underlying request has succeeded. Never construct a shell
   string, evaluate input, or accept arbitrary scripting.
4. Keep system-changing actions medium/high risk; Permissions independently denies
   them without explicit approval. UI visibility is not an authorisation check.
5. Add unit, routing, denial and hostile-input tests using a fake adapter.
6. Add UI payload handling only if needed, and update help/docs.
7. Workflows deliberately allow only open, folder and copy. Expanding that set requires
   a policy review and tests, rather than accepting every new command automatically.

History is a fixed action allowlist and contains no original arguments. Log fixed
messages and exception type names only. Treat a custom executable as trusted code
with the user's full account privileges.
