import contextlib
import logging
from asottile.ordereddict import OrderedDict
from plumbum import local

import pre_commit.constants as C
from pre_commit import five
from pre_commit.clientlib.validate_manifest import load_manifest
from pre_commit.hooks_workspace import in_hooks_workspace
from pre_commit.languages.all import languages
from pre_commit.prefixed_command_runner import PrefixedCommandRunner
from pre_commit.util import cached_property
from pre_commit.util import clean_path_on_failure


logger = logging.getLogger('pre_commit')


class Repository(object):
    def __init__(self, repo_config):
        self.repo_config = repo_config
        self.__created = False
        self.__installed = False

    @cached_property
    def repo_url(self):
        return self.repo_config['repo']

    @cached_property
    def sha(self):
        return self.repo_config['sha']

    @cached_property
    def languages(self):
        return set(hook['language'] for hook in self.hooks.values())

    @cached_property
    def hooks(self):
        return OrderedDict(
            (hook['id'], dict(hook, **self.manifest[hook['id']]))
            for hook in self.repo_config['hooks']
        )

    @cached_property
    def manifest(self):
        with self.in_checkout():
            return dict(
                (hook['id'], hook)
                for hook in load_manifest(C.MANIFEST_FILE)
            )

    def get_cmd_runner(self, hooks_cmd_runner):
        return PrefixedCommandRunner.from_command_runner(
            hooks_cmd_runner, self.sha,
        )

    def require_created(self):
        if self.__created:
            return

        self.create()
        self.__created = True

    def create(self):
        with in_hooks_workspace():
            if local.path(self.sha).exists():
                # Project already exists, no reason to re-create it
                return

            # Checking out environment for the first time
            logger.info('Installing environment for {0}.'.format(self.repo_url))
            logger.info('Once installed this environment will be reused.')
            logger.info('This may take a few minutes...')
            with clean_path_on_failure(five.u(local.path(self.sha))):
                local['git']['clone', '--no-checkout', self.repo_url, self.sha]()
                with self.in_checkout():
                    local['git']['checkout', self.sha]()

    def require_installed(self, cmd_runner):
        if self.__installed:
            return

        self.install(cmd_runner)
        self.__installed = True

    def install(self, cmd_runner):
        """Install the hook repository.

        Args:
            cmd_runner - A `PrefixedCommandRunner` bound to the hooks workspace
        """
        self.require_created()
        repo_cmd_runner = self.get_cmd_runner(cmd_runner)
        for language_name in self.languages:
            language = languages[language_name]
            if (
                language.ENVIRONMENT_DIR is None or
                repo_cmd_runner.exists(language.ENVIRONMENT_DIR)
            ):
                # The language is already installed
                continue
            language.install_environment(repo_cmd_runner)

    @contextlib.contextmanager
    def in_checkout(self):
        self.require_created()
        with in_hooks_workspace():
            with local.cwd(self.sha):
                yield

    def run_hook(self, cmd_runner, hook_id, file_args):
        """Run a hook.

        Args:
            cmd_runner - A `PrefixedCommandRunner` bound to the hooks workspace
            hook_id - Id of the hook
            file_args - List of files to run
        """
        self.require_installed(cmd_runner)
        repo_cmd_runner = self.get_cmd_runner(cmd_runner)
        hook = self.hooks[hook_id]
        return languages[hook['language']].run_hook(
            repo_cmd_runner, hook, file_args,
        )
