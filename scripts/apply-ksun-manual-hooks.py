
from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{label}: expected exactly 1 match, found {count}"
        )
    return text.replace(old, new, 1)


def insert_before(text, marker, content, label):
    return replace_once(text, marker, content + marker, label)


def patch_function(text, start_marker, old, new, label):
    if text.count(start_marker) != 1:
        raise RuntimeError(
            f"{label}: function marker count is "
            f"{text.count(start_marker)}"
        )

    start = text.index(start_marker)
    end = text.find("\n}", start)
    if end < 0:
        raise RuntimeError(f"{label}: function end not found")
    end += 2

    function = text[start:end]
    function = replace_once(function, old, new, label)
    return text[:start] + function + text[end:]


def read_source(path):
    p = Path(path)
    if not p.is_file():
        raise RuntimeError(f"Missing source file: {path}")
    return p, p.read_text()


def write_source(p, text):
    p.write_text(text)
    print(f"Patched {p}")


def patch_exec():
    p, text = read_source("fs/exec.c")
    if "ksu_handle_execveat" in text:
        raise RuntimeError("execve hook already exists in fs/exec.c")

    declaration = (
        "#ifdef CONFIG_KSU\n"
        "__attribute__((hot))\n"
        "extern int ksu_handle_execveat(int *fd, "
        "struct filename **filename_ptr,\n"
        "\t\t\t\tvoid *argv, void *envp, int *flags);\n"
        "#endif\n"
    )
    text = insert_before(
        text,
        "int do_execve(struct filename *filename,\n",
        declaration,
        "execve declaration",
    )

    native_old = (
        "\treturn do_execveat_common(AT_FDCWD, filename, argv, envp, 0);"
    )
    native_new = (
        "#ifdef CONFIG_KSU\n"
        "\tint fd = AT_FDCWD;\n"
        "\tint flags = 0;\n"
        "\tksu_handle_execveat(&fd, &filename, &argv, &envp, &flags);\n"
        "\treturn do_execveat_common(fd, filename, argv, envp, flags);\n"
        "#else\n"
        "\treturn do_execveat_common(AT_FDCWD, filename, argv, envp, 0);\n"
        "#endif"
    )
    text = patch_function(
        text,
        "int do_execve(struct filename *filename,",
        native_old,
        native_new,
        "native execve hook",
    )

    compat_old = (
        "\treturn do_execveat_common(AT_FDCWD, filename, argv, envp, 0);"
    )
    compat_new = (
        "#ifdef CONFIG_KSU\n"
        "\tint fd = AT_FDCWD;\n"
        "\tint flags = 0;\n"
        "\tksu_handle_execveat(&fd, &filename, &argv, &envp, &flags);\n"
        "\treturn do_execveat_common(fd, filename, argv, envp, flags);\n"
        "#else\n"
        "\treturn do_execveat_common(AT_FDCWD, filename, argv, envp, 0);\n"
        "#endif"
    )
    text = patch_function(
        text,
        "static int compat_do_execve(struct filename *filename,",
        compat_old,
        compat_new,
        "compat execve hook",
    )
    write_source(p, text)


def patch_open():
    p, text = read_source("fs/open.c")
    if "ksu_handle_faccessat" in text:
        raise RuntimeError("faccessat hook already exists in fs/open.c")

    declaration = (
        "#ifdef CONFIG_KSU\n"
        "__attribute__((hot))\n"
        "extern int ksu_handle_faccessat(int *dfd, "
        "const char __user **filename_user,\n"
        "\t\t\t\tint *mode, int *flags);\n"
        "#endif\n"
    )
    text = insert_before(
        text,
        "SYSCALL_DEFINE3(faccessat,",
        declaration,
        "faccessat declaration",
    )

    text = replace_once(
        text,
        "\tunsigned int lookup_flags = LOOKUP_FOLLOW;\n"
        "\tif (mode & ~S_IRWXO)",
        "\tunsigned int lookup_flags = LOOKUP_FOLLOW;\n"
        "#ifdef CONFIG_KSU\n"
        "\tksu_handle_faccessat(&dfd, &filename, &mode, NULL);\n"
        "#endif\n"
        "\tif (mode & ~S_IRWXO)",
        "faccessat hook call",
    )
    write_source(p, text)


def patch_read():
    p, text = read_source("fs/read_write.c")
    if "ksu_handle_sys_read" in text:
        raise RuntimeError("read hook already exists in fs/read_write.c")

    declaration = (
        "#ifdef CONFIG_KSU\n"
        "extern bool ksu_vfs_read_hook __read_mostly;\n"
        "extern __attribute__((cold)) int ksu_handle_sys_read("
        "unsigned int fd, char __user **buf_ptr, size_t *count_ptr);\n"
        "#endif\n"
    )
    text = insert_before(
        text,
        "SYSCALL_DEFINE3(read,",
        declaration,
        "read hook declaration",
    )

    text = patch_function(
        text,
        "SYSCALL_DEFINE3(read,",
        "\tssize_t ret = -EBADF;",
        "\tssize_t ret = -EBADF;\n"
        "#ifdef CONFIG_KSU\n"
        "\tif (unlikely(ksu_vfs_read_hook))\n"
        "\t\tksu_handle_sys_read(fd, &buf, &count);\n"
        "#endif",
        "read hook call",
    )
    write_source(p, text)


def patch_stat():
    p, text = read_source("fs/stat.c")
    if "ksu_handle_stat" in text:
        raise RuntimeError("stat hook already exists in fs/stat.c")

    declaration = (
        "#ifdef CONFIG_KSU\n"
        "__attribute__((hot))\n"
        "extern int ksu_handle_stat(int *dfd, "
        "const char __user **filename_user, int *flags);\n"
        "#endif\n"
    )
    text = insert_before(
        text,
        "SYSCALL_DEFINE4(newfstatat,",
        declaration,
        "stat hook declaration",
    )

    text = patch_function(
        text,
        "SYSCALL_DEFINE4(newfstatat,",
        "\tint error;",
        "\tint error;\n"
        "#ifdef CONFIG_KSU\n"
        "\tksu_handle_stat(&dfd, &filename, &flag);\n"
        "#endif",
        "stat hook call",
    )
    write_source(p, text)


def patch_reboot():
    p, text = read_source("kernel/reboot.c")
    if "ksu_handle_sys_reboot" in text:
        raise RuntimeError("reboot hook already exists in kernel/reboot.c")

    declaration = (
        "#ifdef CONFIG_KSU\n"
        "extern int ksu_handle_sys_reboot(int magic1, int magic2, "
        "unsigned int cmd, void __user **arg);\n"
        "#endif\n"
    )
    text = insert_before(
        text,
        "SYSCALL_DEFINE4(reboot,",
        declaration,
        "reboot hook declaration",
    )

    text = patch_function(
        text,
        "SYSCALL_DEFINE4(reboot,",
        "\tint ret = 0;",
        "\tint ret = 0;\n"
        "#ifdef CONFIG_KSU\n"
        "\tksu_handle_sys_reboot(magic1, magic2, cmd, &arg);\n"
        "#endif",
        "reboot hook call",
    )
    write_source(p, text)


def main():
    # Do not leave a partially patched tree if a later hook fails.
    # GitHub Actions builds in a disposable checkout, so a failure
    # safely terminates that run without affecting the repository.
    patch_exec()
    patch_open()
    patch_read()
    patch_stat()
    patch_reboot()
    print("All five Xen-Kernel Manual Hook patches applied.")


if __name__ == "__main__":
    main()