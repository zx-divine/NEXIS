// Read-only shortcut metadata probe for installer verification.
var path = WScript.Arguments(0).replace(/\//g, "\\");
var fso = new ActiveXObject("Scripting.FileSystemObject");
if (!fso.FileExists(path)) throw new Error("Shortcut does not exist");
var shortcut = new ActiveXObject("WScript.Shell").CreateShortcut(path);
var item = new ActiveXObject("Shell.Application").NameSpace(fso.GetParentFolderName(path)).ParseName(fso.GetFileName(path));
WScript.Echo(shortcut.TargetPath);
WScript.Echo(shortcut.IconLocation);
WScript.Echo(item.ExtendedProperty("System.AppUserModel.ID"));
