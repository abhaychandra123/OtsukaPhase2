import { redirect } from "next/navigation";

// The Workspace is now the right pane of the Junior Command Center at /junior.
// Keep this route as a redirect so any saved links / bookmarks don't 404.
export default function JuniorWorkspaceRedirect() {
  redirect("/junior");
}
