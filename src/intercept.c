#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <string.h>

#ifndef PATH_MAX
#  define PATH_MAX 4096
#endif

int chown(const char *path, uid_t owner, gid_t group)
{
    const char *D = getenv("D");                 /* gentoo's image dir */
    const char *autoscript=getenv("AUTOSCRIPT"); /* log of intercepted chowns */
    const char *autorecord=getenv("AUTORECORD"); /* non-null means log cmds */
    const char *fpath;                           /* final path to file */
    char rpath[PATH_MAX];                        /* real full path */
    char catpath[PATH_MAX];                      /* cwd + path */
    int path_max;
    FILE *outf;
    int fpathlen;
    struct stat statbuf;

    /* catch un-set env vars -- this should not happen normally */
    if (D == NULL) D = "";
    if (autoscript == NULL) autoscript = "/tmp/autoscript.sh";
    if (autorecord == NULL) autorecord = "on";

    /* expand path based on current working directory */
    if (path[0] == '/') {
        strcpy(catpath, path);
    }
    else {
        if (getcwd(catpath, sizeof(catpath)) == NULL) {
            printf("!!! failed to get cwd\n");
            return -1;
        }
        strcat(catpath, "/");
        strcat(catpath, path);
    }
    if (realpath(catpath, rpath) == NULL) {
        fprintf(stderr, "!!! failed to get realpath: %s\n", catpath);
        return -1;
    }

    /* find beginning of fpath, after D */
    for (fpathlen=strlen(D)-1; fpathlen>1 ; --fpathlen) {
        if (D[fpathlen] != '/') {
            ++fpathlen;
            break;
        }
    }
    fpath = rpath + fpathlen;

    /* catch bad paths */
    if (strncmp(rpath, D, fpathlen) != 0) {
        fprintf(stderr, "!!! chown outside %s not allowed: %s\n", D, rpath);
        /* should set errno here */
        return -1; /* return error */
    }
    if (stat(rpath, &statbuf) != 0) {
        fprintf(stderr, "!!! during chown, can't stat %s\n", rpath);
        return -1; /* return error */
    }

    /* open autoscript */
    outf = fopen(autoscript, "a");
    if (outf == NULL) {
        fprintf(stderr, "!!! error opening AUTOSCRIPT: %s\n", autoscript);
        /* should set errno here */
        return -1; /* return error */
    }

    /* check the autorecord env var */
    if (strcasecmp(autorecord, "on") == 0) {
        /* check if the file's owner is being set to current euid */
        if (owner == geteuid()) {
            fprintf(outf, "# intercepted but uid is current user: ");
        }
    }
    else if (strcasecmp(autorecord, "off") == 0) {
        fprintf(outf, "# intercepted but AUTORECORD is OFF: ");
    }

    /* write out appropriate command for this attempted chown */
    if (owner == -1)
        if (group == -1)
            fprintf(outf, "# no change to ${D}%s\n", fpath);
        else
            fprintf(outf, "chown :%d ${D}%s\n", group, fpath);
    else
        if (group == -1)
            fprintf(outf, "chown %d ${D}%s\n", owner, fpath);
        else
            fprintf(outf, "chown %d:%d ${D}%s\n", owner, group, fpath);

    fclose(outf);
    return 0;  /* return success */
}
